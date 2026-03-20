# SOIT Codex Phase 8 - Workspace and Settings 1.0

## Goal
补齐 SOIT 1.0 必要的基础配置能力，确保平台主链路具备基本工作空间配置、角色和密钥管理能力。

## Scope
- Workspace base info
- Secrets / API keys basics
- Member and role minimum implementation
- Default platform settings

## Must Follow
- 只做基础能力，不做复杂组织架构
- 不做高级权限系统扩展
- 不做复杂审计和审批流

## Tasks
1. Review workspace and settings domain objects.
2. Build workspace basic info page.
3. Build secrets / API key basic configuration page if not already usable.
4. Implement minimum roles such as admin and member.
5. Add member management basics if data model exists.
6. Add settings for default model, upload limits, and essential runtime config.
7. Verify main workflows can read settings correctly.

## Deliverables
- Workspace page
- Basic settings page
- Basic secret configuration
- Minimum role support

## Acceptance Criteria
- Admin can configure workspace basics
- Platform has minimum role distinction
- Main runtime flows can read settings and defaults

## Suggested Commit
feat(settings): add 1.0 workspace and base configuration capabilities
