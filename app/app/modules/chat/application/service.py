""" service

Chat domain service.
"""

from typing import Optional, List, Dict, Any, AsyncIterator, Callable, Tuple
from datetime import datetime
import asyncio
import hashlib
import json
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.ids import generate_ulid, generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.trace.writer import TraceWriter
from app.kernel.ports.llm.interface import LLMPort, ChatMessage
from app.kernel.observability.idempotency import IdempotencyRepository
from app.modules.chat.domain.models import Conversation, Message
from app.modules.chat.application.config_provider import ChatConfigProvider
from app.modules.chat.application.ports import ConversationRepositoryPort, MessageRepositoryPort
from app.modules.chat.application.schemas import (
    ConversationCreate,
    ConversationUpdate,
    ChatCompletionRequest,
    ChatRagConfig,
)
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_CHAT
from app.modules.dataset.application.schemas import QueryRequest, QueryCitation


class ChatService:
    """Chat domain service."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        conversation_repo: ConversationRepositoryPort,
        message_repo: MessageRepositoryPort,
        llm_port: Optional[LLMPort] = None,
        trace_writer: Optional[TraceWriter] = None,
        config_provider: Optional[ChatConfigProvider] = None,
        dataset_service: Optional["DatasetService"] = None,
        dataset_service_factory: Optional[Callable[[], "DatasetService"]] = None,
    ):
        """Initialize chat service.
        
        Args:
            db: Database session.
            ctx: Request context.
            conversation_repo: Conversation repository.
            message_repo: Message repository.
            llm_port: Optional LLM port.
            trace_writer: Optional trace writer.
        """
        self.db = db
        self.ctx = ctx
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.llm_port = llm_port
        self.trace_writer = trace_writer
        self.config_provider = config_provider
        self.dataset_service = dataset_service
        self.dataset_service_factory = dataset_service_factory
        self._dataset_service_cached: Optional["DatasetService"] = None

    def _resolve_chat_config(self, app_id: Optional[str]) -> Dict[str, Any]:
        if not self.config_provider:
            return {}
        _, _, spec = self.config_provider.resolve(app_id)
        return spec or {}

    def _normalize_model_ref(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if value.startswith("model:"):
            return value
        if ":" in value:
            return f"model:{value}"
        return f"model:{value}"

    def _normalize_rag_spec(self, rag: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not rag or not isinstance(rag, dict):
            return None
        payload = dict(rag)
        if "datasets" in payload and "dataset_ids" not in payload:
            payload["dataset_ids"] = payload.get("datasets")
        return payload

    def _resolve_spec_defaults(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        model_ref = spec.get("model_ref")
        model = spec.get("model")
        model_params: Dict[str, Any] = {}
        if not model_ref:
            if isinstance(model, str):
                model_ref = model
            elif isinstance(model, dict):
                model_ref = model.get("ref_key")
                if not model_ref:
                    provider = model.get("provider")
                    model_name = model.get("model")
                    if provider and model_name:
                        model_ref = f"model:{provider}:{model_name}"
                model_params = model.get("params") or {}
        model_ref = self._normalize_model_ref(model_ref) if model_ref else None
        limits = spec.get("limits") or {}
        return {
            "system_prompt": spec.get("system_prompt"),
            "model_ref": model_ref,
            "temperature": spec.get("temperature") if spec.get("temperature") is not None else model_params.get("temperature"),
            "max_tokens": (
                spec.get("max_tokens")
                if spec.get("max_tokens") is not None
                else limits.get("max_tokens")
                if limits.get("max_tokens") is not None
                else model_params.get("max_tokens")
            ),
            "top_p": spec.get("top_p") if spec.get("top_p") is not None else model_params.get("top_p"),
            "tool_refs": spec.get("tool_refs") or (spec.get("tools") or {}).get("allowlist"),
            "rag": self._normalize_rag_spec(spec.get("rag")),
            "limits": limits,
        }

    def _ensure_conversation_app(self, conversation: Conversation) -> Dict[str, Any]:
        """Ensure conversation has app_id and return resolved spec."""
        if not self.config_provider:
            return {}
        if conversation.app_id:
            _, _, spec = self.config_provider.resolve(conversation.app_id)
            return spec or {}
        app, _version, spec = self.config_provider.resolve(None)
        conversation.app_id = app.id
        self.db.commit()
        self.db.refresh(conversation)
        return spec or {}

    def _get_dataset_service(self) -> Optional["DatasetService"]:
        """Resolve dataset service lazily."""
        if self.dataset_service is not None:
            return self.dataset_service
        if self._dataset_service_cached is not None:
            return self._dataset_service_cached
        if self.dataset_service_factory is None:
            return None
        self._dataset_service_cached = self.dataset_service_factory()
        return self._dataset_service_cached

    def _extract_latest_user_message(self, messages: List[ChatMessage]) -> Optional[str]:
        """Extract latest user message content."""
        for msg in reversed(messages):
            if msg.role == "user" and msg.content:
                return msg.content.strip()
        return None

    def _format_rag_context(
        self,
        citations: List[QueryCitation],
        fallback_text: Dict[str, str],
    ) -> str:
        """Format dataset citations into a system prompt."""
        if not citations:
            return ""
        lines: List[str] = []
        for idx, citation in enumerate(citations, start=1):
            snippet = citation.snippet or fallback_text.get(citation.chunk_id) or ""
            if not snippet:
                continue
            source = citation.title or citation.doc_key or citation.document_id or citation.chunk_id
            dataset_id = citation.dataset_id or "unknown"
            lines.append(f"[{idx}] {snippet} (source: {source}; dataset: {dataset_id})")
        if not lines:
            return ""
        header = "Use the following dataset snippets to answer the user. Cite sources by [number] when relevant."
        return header + "\n" + "\n".join(lines)

    def _inject_rag_message(self, messages: List[ChatMessage], content: str) -> List[ChatMessage]:
        """Inject RAG system message after leading system prompts."""
        if not content:
            return messages
        insert_at = 0
        for idx, msg in enumerate(messages):
            if msg.role == "system":
                insert_at = idx + 1
            else:
                break
        return messages[:insert_at] + [ChatMessage(role="system", content=content)] + messages[insert_at:]

    def _is_deep_thinking_enabled(self, metadata: Optional[Dict[str, Any]]) -> bool:
        """Resolve deep thinking toggle from request metadata."""
        if not isinstance(metadata, dict):
            return False
        candidates = (
            metadata.get("deep_thinking"),
            metadata.get("deepThinking"),
            metadata.get("reasoning_mode"),
            metadata.get("reasoningMode"),
        )
        for value in candidates:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return int(value) == 1
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "on", "yes", "enabled"}:
                    return True
                if normalized in {"0", "false", "off", "no", "disabled"}:
                    return False
        return False

    def _resolve_reasoning_effort(self, metadata: Optional[Dict[str, Any]]) -> Optional[str]:
        """Resolve reasoning effort from request metadata."""
        if not isinstance(metadata, dict):
            return None
        value = metadata.get("reasoning_effort")
        if value is None:
            value = metadata.get("reasoningEffort")
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"low", "medium", "high"}:
            return normalized
        return None

    def _inject_deep_thinking_prompt(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """Inject prompt that asks model to emit visible reasoning blocks."""
        prompt = (
            "Deep thinking mode is enabled. First write your reasoning in a <think>...</think> block. "
            "Then write the final answer outside of the <think> block."
        )
        return self._inject_rag_message(messages, prompt)

    async def _apply_rag(
        self,
        data: ChatCompletionRequest,
        messages: List[ChatMessage],
        rag_override: Optional[ChatRagConfig] = None,
    ) -> Tuple[List[ChatMessage], Dict[str, Any]]:
        """Apply dataset retrieval context if configured."""
        rag = rag_override or data.rag
        if not rag or not rag.dataset_ids:
            return messages, {}
        dataset_service = self._get_dataset_service()
        if not dataset_service:
            raise ValidationError("Dataset service not configured for RAG")

        query_text = (rag.query or self._extract_latest_user_message(messages) or "").strip()
        if not query_text:
            raise ValidationError("RAG requires rag.query or a user message")

        citations: List[QueryCitation] = []
        fallback_text: Dict[str, str] = {}
        dataset_ids = list(dict.fromkeys([ds for ds in rag.dataset_ids if ds]))
        for dataset_id in dataset_ids:
            query_request = QueryRequest(
                query=query_text,
                top_k=rag.top_k,
                index_id=rag.index_id,
                index_ids=rag.index_ids,
                filter=rag.filter,
                use_rerank=rag.use_rerank,
                reranker_ref=rag.reranker_ref,
                strategy=rag.strategy,
                include_snippets=rag.include_snippets,
                snippet_length=rag.snippet_length,
                max_snippets=rag.max_snippets,
                keyword_top_k=rag.keyword_top_k,
                keyword_candidate_limit=rag.keyword_candidate_limit,
                keyword_min_score=rag.keyword_min_score,
                hybrid_alpha=rag.hybrid_alpha,
            )
            response = await dataset_service.query(dataset_id, query_request)
            for result in response.results:
                if result.text:
                    fallback_text[result.chunk_id] = result.text
            citations.extend(response.citations)

        rag_context = self._format_rag_context(citations, fallback_text)
        messages = self._inject_rag_message(messages, rag_context)

        metadata = {
            "citations": [item.model_dump() for item in citations],
            "rag_query": query_text,
            "rag_datasets": dataset_ids,
        }
        return messages, metadata
    
    def _resolve_completion_resource_id(self, data: ChatCompletionRequest, **kwargs) -> str:
        """Resolve conversation id for completion RBAC checks."""
        if data.conversation_id:
            return data.conversation_id
        return f"new:{self.ctx.workspace_id}"

    def _resolve_create_resource_id(self, data: ConversationCreate, **kwargs) -> str:
        """Resolve conversation id for create RBAC checks."""
        return f"new:{self.ctx.workspace_id}"

    @rbac_guard(RESOURCE_CHAT, "create", resource_id_resolver=_resolve_create_resource_id)
    async def create_conversation(
        self,
        data: ConversationCreate,
    ) -> Conversation:
        """Create a new conversation.
        
        Args:
            data: Conversation creation data.
            
        Returns:
            Created Conversation instance.
        """
        spec = self._resolve_chat_config(None)
        defaults = self._resolve_spec_defaults(spec)
        app_id = None
        if self.config_provider:
            app_id = self.config_provider.resolve(None)[0].id
        conversation = Conversation(
            id=generate_ulid(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            title=data.title,
            status=data.status,
            metadata_json=data.metadata,
            app_id=app_id,
            system_prompt=data.system_prompt if data.system_prompt is not None else defaults.get("system_prompt"),
            default_model_ref=data.default_model_ref or defaults.get("model_ref"),
            default_temperature=(
                data.default_temperature if data.default_temperature is not None else defaults.get("temperature")
            ),
            default_max_tokens=(
                data.default_max_tokens if data.default_max_tokens is not None else defaults.get("max_tokens")
            ),
            default_top_p=(
                data.default_top_p if data.default_top_p is not None else defaults.get("top_p")
            ),
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )
        
        return self.conversation_repo.create(conversation)

    @rbac_guard(RESOURCE_CHAT, "update", resource_id_arg="conversation_id")
    async def update_conversation(
        self,
        conversation_id: str,
        data: ConversationUpdate,
    ) -> Conversation:
        """Update a conversation.

        Args:
            conversation_id: Conversation ID.
            data: Conversation update data.

        Returns:
            Updated Conversation instance.
        """
        return self.conversation_repo.update(
            conversation_id=conversation_id,
            title=data.title,
            metadata=data.metadata,
            status=data.status,
            system_prompt=data.system_prompt,
            default_model_ref=data.default_model_ref,
            default_temperature=data.default_temperature,
            default_max_tokens=data.default_max_tokens,
            default_top_p=data.default_top_p,
            updated_by=self.ctx.user_id,
        )
    
    @rbac_guard(RESOURCE_CHAT, "update", resource_id_arg="conversation_id")
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        model_ref: Optional[str] = None,
        tokens_prompt: Optional[int] = None,
        tokens_completion: Optional[int] = None,
        finish_reason: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Message:
        """Add a message to a conversation.
        
        Args:
            conversation_id: Conversation ID.
            role: Message role (user, assistant, system).
            content: Message content.
            metadata: Optional message metadata.
            
        Returns:
            Created Message instance.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        # Verify conversation exists
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        
        # Create message
        message = Message(
            id=generate_ulid(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            conversation_id=conversation_id,
            parent_id=parent_id,
            role=role,
            content=content,
            model_ref=model_ref,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            finish_reason=finish_reason,
            run_id=run_id,
            created_by=self.ctx.user_id,
            metadata_json=metadata,
        )
        
        message = self.message_repo.create(message)
        
        # Update conversation stats
        conversation.updated_at = utc_now()
        conversation.updated_by = self.ctx.user_id
        conversation.last_message_at = utc_now()
        if conversation.message_count is None:
            conversation.message_count = 0
        conversation.message_count += 1
        self.db.commit()
        self.db.refresh(conversation)
        
        return message
    
    @rbac_guard(RESOURCE_CHAT, "read", resource_id_arg="conversation_id")
    async def get_conversation(self, conversation_id: str) -> Conversation:
        """Get conversation by ID.
        
        Args:
            conversation_id: Conversation ID.
            
        Returns:
            Conversation instance.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        return conversation
    
    @workspace_guard("read")
    async def list_conversations(
        self,
        limit: int = 20,
        offset: int = 0,
        cursor_at: Optional[datetime] = None,
        cursor_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Conversation]:
        """List conversations.
        
        Args:
            limit: Maximum number of conversations.
            offset: Offset for pagination.
            cursor_at: Updated_at cursor for pagination.
            cursor_id: Conversation ID cursor for pagination.
            
        Returns:
            List of Conversation instances.
        """
        return self.conversation_repo.list(
            limit=limit,
            offset=offset,
            cursor_at=cursor_at,
            cursor_id=cursor_id,
            status=status,
        )
    
    @rbac_guard(RESOURCE_CHAT, "read", resource_id_arg="conversation_id")
    async def get_messages(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
        cursor_at: Optional[datetime] = None,
        cursor_id: Optional[str] = None,
    ) -> List[Message]:
        """Get messages in a conversation.
        
        Args:
            conversation_id: Conversation ID.
            limit: Maximum number of messages.
            offset: Offset for pagination.
            cursor_at: Created_at cursor for pagination.
            cursor_id: Message ID cursor for pagination.
            
        Returns:
            List of Message instances.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        # Verify conversation exists
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation not found: {conversation_id}")
        
        return self.message_repo.list_by_conversation(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
            cursor_at=cursor_at,
            cursor_id=cursor_id,
        )

    def _resolve_parent_message(
        self,
        conversation_id: str,
        parent_message_id: Optional[str],
    ) -> Optional[Message]:
        """Resolve parent/base message for a completion run."""
        if parent_message_id:
            parent_message = self.message_repo.get_by_id(parent_message_id)
            if not parent_message or parent_message.conversation_id != conversation_id:
                raise ValidationError(f"Parent message not found: {parent_message_id}")
            return parent_message

        return self.message_repo.get_latest_by_conversation(conversation_id)

    def _resolve_history_messages(
        self,
        conversation_id: str,
        history_limit: int,
        head_message_id: Optional[str],
    ) -> List[Message]:
        """Load branch history (root->head) for a conversation.

        Args:
            conversation_id: Conversation ID.
            history_limit: Max messages to include.
            head_message_id: Branch head message ID.

        Returns:
            List of Message instances (oldest to newest).
        """
        if history_limit <= 0 or not head_message_id:
            return []
        return self.message_repo.list_ancestry(
            conversation_id=conversation_id,
            head_message_id=head_message_id,
            limit=history_limit,
        )

    def _infer_title(self, messages: List[ChatMessage]) -> Optional[str]:
        """Infer a short title from messages.

        Args:
            messages: Chat messages.

        Returns:
            Short title or None.
        """
        for msg in messages:
            if msg.role == "user" and msg.content:
                return msg.content.strip()[:80]
        return None

    def _hash_request(self, data: ChatCompletionRequest) -> str:
        """Create a deterministic hash for idempotency checks."""
        payload = data.model_dump(
            exclude={"stream", "stream_chunk_size"},
            exclude_none=True,
        )
        normalized = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _load_idempotency_result(self, response_json: Dict[str, Any]) -> Dict[str, Any]:
        """Load cached completion result from idempotency response."""
        if not response_json:
            raise ValidationError("Idempotency response missing")

        conversation_id = response_json.get("conversation_id")
        message_id = response_json.get("message_id")
        if not conversation_id or not message_id:
            raise ValidationError("Idempotency response incomplete")

        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation not found: {conversation_id}")

        message = self.message_repo.get_by_id(message_id)
        if not message:
            raise NotFoundError(f"Message not found: {message_id}")

        return {
            "run_id": response_json.get("run_id"),
            "conversation": conversation,
            "message": message,
            "model": response_json.get("model"),
            "tokens_prompt": response_json.get("tokens_prompt"),
            "tokens_completion": response_json.get("tokens_completion"),
            "finish_reason": response_json.get("finish_reason"),
        }

    @rbac_guard(RESOURCE_CHAT, "run", resource_id_resolver=_resolve_completion_resource_id)
    async def create_completion(
        self,
        data: ChatCompletionRequest,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a chat completion and persist messages.

        Args:
            data: Chat completion request data.

        Returns:
            Completion result dictionary.
        """
        if not self.llm_port:
            raise ValidationError("LLM gateway not available")

        idempotency_repo = None
        idempotency_record = None
        rag_meta: Dict[str, Any] = {}
        if idempotency_key:
            idempotency_repo = IdempotencyRepository(self.db, self.ctx)
            request_hash = self._hash_request(data)
            existing = idempotency_repo.get("chat.completions", idempotency_key)
            if existing:
                if existing.request_hash != request_hash:
                    raise ValidationError("Idempotency key conflicts with a different request")
                if existing.status == "completed":
                    return self._load_idempotency_result(existing.response_json or {})
                if existing.status == "in_progress":
                    raise ValidationError("Idempotency key already in progress")
                idempotency_record = idempotency_repo.mark_in_progress(existing)
            else:
                idempotency_record = idempotency_repo.create_in_progress(
                    "chat.completions",
                    idempotency_key,
                    request_hash,
                )

        run_id = None
        parent_message: Optional[Message] = None
        deep_thinking_enabled = False
        reasoning_effort: Optional[str] = None
        try:
            conversation: Optional[Conversation] = None
            if data.conversation_id:
                conversation = self.conversation_repo.get_by_id(data.conversation_id)
                if not conversation:
                    raise NotFoundError(f"Conversation not found: {data.conversation_id}")
            else:
                conversation = await self.create_conversation(
                    ConversationCreate(title=data.title, metadata=data.metadata)
                )

            spec = self._ensure_conversation_app(conversation)
            defaults = self._resolve_spec_defaults(spec)
            rag_override = None
            if data.rag is None and defaults.get("rag"):
                rag_override = ChatRagConfig.model_validate(defaults.get("rag"))

            parent_message = self._resolve_parent_message(
                conversation_id=conversation.id,
                parent_message_id=data.parent_message_id,
            )
            history_messages = self._resolve_history_messages(
                conversation_id=conversation.id,
                history_limit=data.history_limit,
                head_message_id=parent_message.id if parent_message else None,
            )

            llm_messages = [
                ChatMessage(role=msg.role, content=msg.content)
                for msg in history_messages
            ]
            llm_messages.extend(
                ChatMessage(role=msg.role, content=msg.content)
                for msg in data.messages
            )

            system_prompt = conversation.system_prompt or defaults.get("system_prompt")
            if system_prompt and not any(msg.role == "system" for msg in llm_messages):
                llm_messages = [ChatMessage(role="system", content=system_prompt)] + llm_messages

            llm_messages, rag_meta = await self._apply_rag(data, llm_messages, rag_override=rag_override)

            deep_thinking_enabled = self._is_deep_thinking_enabled(data.metadata)
            reasoning_effort = self._resolve_reasoning_effort(data.metadata)
            if deep_thinking_enabled:
                llm_messages = self._inject_deep_thinking_prompt(llm_messages)
                if reasoning_effort is None:
                    reasoning_effort = "high"

            if not llm_messages:
                raise ValidationError("No messages provided for completion")

            run_id = generate_run_id()
            if self.trace_writer:
                if not self.config_provider:
                    raise ValidationError("Chat config provider is required for run tracking")
                app, version, _ = self.config_provider.resolve(conversation.app_id)
                run = self.trace_writer.create_run(
                    mode="chat",
                    app_id=app.id,
                    app_version_id=version.id,
                    app_type="chat",
                    input_summary=llm_messages[-1].content[:8192],
                    run_id=run_id,
                )
                run_id = run.id
                self.trace_writer.update_run_status(run_id, "running")
        except Exception:
            if idempotency_record and idempotency_repo:
                idempotency_repo.mark_failed(idempotency_record)
            raise

        current_parent_id = parent_message.id if parent_message else None
        try:
            for msg in data.messages:
                stored = await self.add_message(
                    conversation_id=conversation.id,
                    role=msg.role,
                    content=msg.content,
                    metadata=msg.metadata,
                    parent_id=current_parent_id,
                    run_id=run_id,
                )
                current_parent_id = stored.id

            if not conversation.title:
                inferred_title = self._infer_title(llm_messages)
                if inferred_title:
                    self.conversation_repo.update(
                        conversation_id=conversation.id,
                        title=inferred_title,
                        metadata=conversation.metadata_json,
                    )

            model_ref = (
                data.model
                or conversation.default_model_ref
                or defaults.get("model_ref")
                or "model:openai:gpt-5.1"
            )
            temperature = (
                data.temperature
                if data.temperature is not None
                else conversation.default_temperature
                if conversation.default_temperature is not None
                else defaults.get("temperature")
            )
            max_tokens = (
                data.max_tokens
                if data.max_tokens is not None
                else conversation.default_max_tokens
                if conversation.default_max_tokens is not None
                else defaults.get("max_tokens")
            )
            top_p = (
                data.top_p
                if data.top_p is not None
                else conversation.default_top_p
                if conversation.default_top_p is not None
                else defaults.get("top_p")
            )

            response = await self.llm_port.chat(
                messages=llm_messages,
                model=model_ref,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                reasoning_effort=reasoning_effort,
                run_id=run_id,
            )

            message_metadata = {
                "model": response.model or model_ref,
                "tokens_prompt": response.tokens_prompt,
                "tokens_completion": response.tokens_completion,
                "finish_reason": response.finish_reason,
                "run_id": run_id,
            }
            if rag_meta:
                message_metadata.update(rag_meta)
            if deep_thinking_enabled:
                message_metadata["deep_thinking"] = True
            if reasoning_effort:
                message_metadata["reasoning_effort"] = reasoning_effort

            assistant_message = await self.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=response.text,
                parent_id=current_parent_id,
                model_ref=response.model or model_ref,
                tokens_prompt=response.tokens_prompt,
                tokens_completion=response.tokens_completion,
                finish_reason=response.finish_reason,
                run_id=run_id,
                metadata=message_metadata,
            )

            if self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "succeeded",
                    output_summary=response.text[:8192] if response.text else None,
                )

            if idempotency_record and idempotency_repo:
                idempotency_repo.update_response(
                    idempotency_record,
                    {
                        "run_id": run_id,
                        "conversation_id": conversation.id,
                        "message_id": assistant_message.id,
                        "model": response.model or model_ref,
                        "tokens_prompt": response.tokens_prompt,
                        "tokens_completion": response.tokens_completion,
                        "finish_reason": response.finish_reason,
                    },
                )

            return {
                "run_id": run_id,
                "conversation": conversation,
                "message": assistant_message,
                "model": response.model or model_ref,
                "tokens_prompt": response.tokens_prompt,
                "tokens_completion": response.tokens_completion,
                "finish_reason": response.finish_reason,
            }
        except Exception as exc:
            if idempotency_record and idempotency_repo:
                idempotency_repo.mark_failed(idempotency_record)
            if self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "failed",
                    output_summary=str(exc)[:8192],
                )
            raise

    @rbac_guard(RESOURCE_CHAT, "run", resource_id_resolver=_resolve_completion_resource_id)
    async def stream_completion(
        self,
        data: ChatCompletionRequest,
        idempotency_key: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream chat completion and persist messages."""
        if not self.llm_port:
            raise ValidationError("LLM gateway not available")

        conversation: Optional[Conversation] = None
        assistant_text = ""
        tokens_prompt = 0
        tokens_completion = 0
        finish_reason = None
        model_used = None
        assistant_saved = False
        rag_meta: Dict[str, Any] = {}
        parent_message: Optional[Message] = None

        idempotency_repo = None
        idempotency_record = None
        if idempotency_key:
            idempotency_repo = IdempotencyRepository(self.db, self.ctx)
            request_hash = self._hash_request(data)
            existing = idempotency_repo.get("chat.stream", idempotency_key)
            if existing:
                if existing.request_hash != request_hash:
                    raise ValidationError("Idempotency key conflicts with a different request")
                if existing.status == "completed":
                    cached = self._load_idempotency_result(existing.response_json or {})
                    cached_message = cached["message"]
                    cached_run_id = cached["run_id"]
                    cached_conversation = cached["conversation"]
                    yield {
                        "type": "start",
                        "run_id": cached_run_id,
                        "conversation_id": cached_conversation.id,
                    }
                    if cached_message.content:
                        yield {
                            "type": "delta",
                            "run_id": cached_run_id,
                            "delta": cached_message.content,
                        }
                    yield {
                        "type": "complete",
                        "run_id": cached_run_id,
                        "message": cached_message,
                        "model": cached["model"],
                        "tokens_prompt": cached["tokens_prompt"],
                        "tokens_completion": cached["tokens_completion"],
                        "finish_reason": cached["finish_reason"],
                    }
                    return
                if existing.status == "in_progress":
                    raise ValidationError("Idempotency key already in progress")
                idempotency_record = idempotency_repo.mark_in_progress(existing)
            else:
                idempotency_record = idempotency_repo.create_in_progress(
                    "chat.stream",
                    idempotency_key,
                    request_hash,
                )

        run_id = None
        deep_thinking_enabled = False
        reasoning_effort: Optional[str] = None
        try:
            if data.conversation_id:
                conversation = self.conversation_repo.get_by_id(data.conversation_id)
                if not conversation:
                    raise NotFoundError(f"Conversation not found: {data.conversation_id}")
            else:
                conversation = await self.create_conversation(
                    ConversationCreate(title=data.title, metadata=data.metadata)
                )

            spec = self._ensure_conversation_app(conversation)
            defaults = self._resolve_spec_defaults(spec)
            rag_override = None
            if data.rag is None and defaults.get("rag"):
                rag_override = ChatRagConfig.model_validate(defaults.get("rag"))

            parent_message = self._resolve_parent_message(
                conversation_id=conversation.id,
                parent_message_id=data.parent_message_id,
            )
            history_messages = self._resolve_history_messages(
                conversation_id=conversation.id,
                history_limit=data.history_limit,
                head_message_id=parent_message.id if parent_message else None,
            )

            llm_messages = [
                ChatMessage(role=msg.role, content=msg.content)
                for msg in history_messages
            ]
            llm_messages.extend(
                ChatMessage(role=msg.role, content=msg.content)
                for msg in data.messages
            )

            system_prompt = conversation.system_prompt or defaults.get("system_prompt")
            if system_prompt and not any(msg.role == "system" for msg in llm_messages):
                llm_messages = [ChatMessage(role="system", content=system_prompt)] + llm_messages

            llm_messages, rag_meta = await self._apply_rag(data, llm_messages, rag_override=rag_override)

            deep_thinking_enabled = self._is_deep_thinking_enabled(data.metadata)
            reasoning_effort = self._resolve_reasoning_effort(data.metadata)
            if deep_thinking_enabled:
                llm_messages = self._inject_deep_thinking_prompt(llm_messages)
                if reasoning_effort is None:
                    reasoning_effort = "high"

            if not llm_messages:
                raise ValidationError("No messages provided for completion")

            run_id = generate_run_id()
            if self.trace_writer:
                if not self.config_provider:
                    raise ValidationError("Chat config provider is required for run tracking")
                app, version, _ = self.config_provider.resolve(conversation.app_id)
                run = self.trace_writer.create_run(
                    mode="chat",
                    app_id=app.id,
                    app_version_id=version.id,
                    app_type="chat",
                    input_summary=llm_messages[-1].content[:8192],
                    run_id=run_id,
                )
                run_id = run.id
                self.trace_writer.update_run_status(run_id, "running")
        except Exception:
            if idempotency_record and idempotency_repo:
                idempotency_repo.mark_failed(idempotency_record)
            raise

        current_parent_id = parent_message.id if parent_message else None
        try:
            for msg in data.messages:
                stored = await self.add_message(
                    conversation_id=conversation.id,
                    role=msg.role,
                    content=msg.content,
                    metadata=msg.metadata,
                    parent_id=current_parent_id,
                    run_id=run_id,
                )
                current_parent_id = stored.id

            if not conversation.title:
                inferred_title = self._infer_title(llm_messages)
                if inferred_title:
                    self.conversation_repo.update(
                        conversation_id=conversation.id,
                        title=inferred_title,
                        metadata=conversation.metadata_json,
                    )

            model_ref = (
                data.model
                or conversation.default_model_ref
                or defaults.get("model_ref")
                or "model:openai:gpt-5.1"
            )
            temperature = (
                data.temperature
                if data.temperature is not None
                else conversation.default_temperature
                if conversation.default_temperature is not None
                else defaults.get("temperature")
            )
            max_tokens = (
                data.max_tokens
                if data.max_tokens is not None
                else conversation.default_max_tokens
                if conversation.default_max_tokens is not None
                else defaults.get("max_tokens")
            )
            top_p = (
                data.top_p
                if data.top_p is not None
                else conversation.default_top_p
                if conversation.default_top_p is not None
                else defaults.get("top_p")
            )

            stream = None
            try:
                stream = self.llm_port.stream_chat(
                    messages=llm_messages,
                    model=model_ref,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    reasoning_effort=reasoning_effort,
                    run_id=run_id,
                )
            except (NotImplementedError, ValueError, ValidationError):
                stream = None

            if not stream:
                yield {
                    "type": "start",
                    "run_id": run_id,
                    "conversation_id": conversation.id,
                }
                response = await self.llm_port.chat(
                    messages=llm_messages,
                    model=model_ref,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    reasoning_effort=reasoning_effort,
                    run_id=run_id,
                )
                message_metadata = {
                    "model": response.model or model_ref,
                    "tokens_prompt": response.tokens_prompt,
                    "tokens_completion": response.tokens_completion,
                    "finish_reason": response.finish_reason,
                    "run_id": run_id,
                }
                if rag_meta:
                    message_metadata.update(rag_meta)
                if deep_thinking_enabled:
                    message_metadata["deep_thinking"] = True
                if reasoning_effort:
                    message_metadata["reasoning_effort"] = reasoning_effort

                assistant_message = await self.add_message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=response.text,
                    parent_id=current_parent_id,
                    model_ref=response.model or model_ref,
                    tokens_prompt=response.tokens_prompt,
                    tokens_completion=response.tokens_completion,
                    finish_reason=response.finish_reason,
                    run_id=run_id,
                    metadata=message_metadata,
                )
                assistant_saved = True

                if self.trace_writer:
                    self.trace_writer.update_run_status(
                        run_id,
                        "succeeded",
                        output_summary=response.text[:8192] if response.text else None,
                    )
                if idempotency_record and idempotency_repo:
                    idempotency_repo.update_response(
                        idempotency_record,
                        {
                            "run_id": run_id,
                            "conversation_id": conversation.id,
                            "message_id": assistant_message.id,
                            "model": response.model or model_ref,
                            "tokens_prompt": response.tokens_prompt,
                            "tokens_completion": response.tokens_completion,
                            "finish_reason": response.finish_reason,
                        },
                    )
                yield {
                    "type": "delta",
                    "run_id": run_id,
                    "delta": response.text,
                }
                yield {
                    "type": "complete",
                    "run_id": run_id,
                    "message": assistant_message,
                    "model": response.model or model_ref,
                    "tokens_prompt": response.tokens_prompt,
                    "tokens_completion": response.tokens_completion,
                    "finish_reason": response.finish_reason,
                }
                return

            yield {
                "type": "start",
                "run_id": run_id,
                "conversation_id": conversation.id,
            }

            async for chunk in stream:
                if chunk.delta:
                    assistant_text += chunk.delta
                    yield {
                        "type": "delta",
                        "run_id": run_id,
                        "delta": chunk.delta,
                    }
                if chunk.tokens_prompt:
                    tokens_prompt = chunk.tokens_prompt
                if chunk.tokens_completion:
                    tokens_completion = chunk.tokens_completion
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
                if chunk.model:
                    model_used = chunk.model

            message_metadata = {
                "model": model_used or model_ref,
                "tokens_prompt": tokens_prompt,
                "tokens_completion": tokens_completion,
                "finish_reason": finish_reason,
                "run_id": run_id,
            }
            if rag_meta:
                message_metadata.update(rag_meta)
            if deep_thinking_enabled:
                message_metadata["deep_thinking"] = True
            if reasoning_effort:
                message_metadata["reasoning_effort"] = reasoning_effort

            assistant_message = await self.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                parent_id=current_parent_id,
                model_ref=model_used or model_ref,
                tokens_prompt=tokens_prompt or None,
                tokens_completion=tokens_completion or None,
                finish_reason=finish_reason,
                run_id=run_id,
                metadata=message_metadata,
            )
            assistant_saved = True

            if self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "succeeded",
                    output_summary=assistant_text[:8192] if assistant_text else None,
                )

            if idempotency_record and idempotency_repo:
                idempotency_repo.update_response(
                    idempotency_record,
                    {
                        "run_id": run_id,
                        "conversation_id": conversation.id,
                        "message_id": assistant_message.id,
                        "model": model_used or model_ref,
                        "tokens_prompt": tokens_prompt,
                        "tokens_completion": tokens_completion,
                        "finish_reason": finish_reason,
                    },
                )

            yield {
                "type": "complete",
                "run_id": run_id,
                "message": assistant_message,
                "model": model_used or model_ref,
                "tokens_prompt": tokens_prompt,
                "tokens_completion": tokens_completion,
                "finish_reason": finish_reason,
            }
        except asyncio.CancelledError:
            if idempotency_record and idempotency_repo:
                idempotency_repo.mark_failed(idempotency_record)
            if not assistant_saved and assistant_text and conversation:
                try:
                    await self.add_message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=assistant_text,
                        parent_id=current_parent_id,
                        model_ref=model_used or None,
                        tokens_prompt=tokens_prompt or None,
                        tokens_completion=tokens_completion or None,
                        finish_reason="canceled",
                        run_id=run_id,
                        metadata={
                            "model": model_used or None,
                            "tokens_prompt": tokens_prompt,
                            "tokens_completion": tokens_completion,
                            "finish_reason": "canceled",
                            "run_id": run_id,
                            "interrupted": True,
                            **(rag_meta or {}),
                        },
                    )
                except Exception:
                    pass
            if self.trace_writer and run_id:
                output_summary = assistant_text[:8192] if assistant_text else None
                self.trace_writer.update_run_status(run_id, "canceled", output_summary=output_summary)
            raise
        except Exception as exc:
            if idempotency_record and idempotency_repo:
                idempotency_repo.mark_failed(idempotency_record)
            if not assistant_saved and assistant_text and conversation:
                try:
                    await self.add_message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=assistant_text,
                        parent_id=current_parent_id,
                        model_ref=model_used or None,
                        tokens_prompt=tokens_prompt or None,
                        tokens_completion=tokens_completion or None,
                        finish_reason=finish_reason or "error",
                        run_id=run_id,
                        metadata={
                            "model": model_used or None,
                            "tokens_prompt": tokens_prompt,
                            "tokens_completion": tokens_completion,
                            "finish_reason": finish_reason or "error",
                            "run_id": run_id,
                            "interrupted": True,
                            "error": str(exc)[:512],
                            **(rag_meta or {}),
                        },
                    )
                except Exception:
                    pass
            if self.trace_writer:
                self.trace_writer.update_run_status(
                    run_id,
                    "failed",
                    output_summary=str(exc)[:8192],
                )
            raise
    
    @rbac_guard(RESOURCE_CHAT, "delete", resource_id_arg="conversation_id")
    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation (soft delete).
        
        Args:
            conversation_id: Conversation ID.
            
        Raises:
            NotFoundError: If conversation not found.
        """
        self.conversation_repo.soft_delete(conversation_id)
