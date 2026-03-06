"use client";

import { type PropsWithChildren, useEffect, useState, type FC } from "react";
import { cn } from "@/lib/utils";
import { CircleXIcon, FileIcon, PaperclipIcon } from "lucide-react";
import {
  AttachmentPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  useAuiState,
} from "@assistant-ui/react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Dialog,
  DialogTitle,
  DialogTrigger,
  DialogOverlay,
  DialogPortal,
} from "@/components/ui/dialog";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { TooltipIconButton } from "@/components/ui/chat/tooltip-icon-button";
import { Tooltip as TooltipPrimitive, Dialog as DialogPrimitive } from "radix-ui";

const useFileSrc = (file: File | undefined) => {
  const [src, setSrc] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!file) {
      setSrc(undefined);
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    setSrc(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [file]);

  return src;
};

const useAttachmentSrc = () => {
  const { file, src } = useAuiState(({ attachment }): { file?: File; src?: string } => {
    if (attachment.type !== "image") return {};
    if (attachment.file) return { file: attachment.file };
    const src = attachment.content?.filter((c) => c.type === "image")[0]?.image;
    if (!src) return {};
    return { src };
  });

  return useFileSrc(file) ?? src;
};

type AttachmentPreviewProps = {
  src: string;
};

const AttachmentPreview: FC<AttachmentPreviewProps> = ({ src }) => {
  const [isLoaded, setIsLoaded] = useState(false);

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      style={{
        width: "auto",
        height: "auto",
        maxWidth: "75dvh",
        maxHeight: "75dvh",
        display: isLoaded ? "block" : "none",
        overflow: "clip",
      }}
      onLoad={() => setIsLoaded(true)}
      alt="Preview"
    />
  );
};

const AttachmentPreviewDialog: FC<PropsWithChildren> = ({ children }) => {
  const src = useAttachmentSrc();

  if (!src) return children;

  return (
    <Dialog>
      <DialogTrigger className="hover:bg-accent/50 cursor-pointer transition-colors" asChild>
        {children}
      </DialogTrigger>
      <AttachmentDialogContent>
        <DialogTitle className="aui-sr-only">
          Image Attachment Preview
        </DialogTitle>
        <AttachmentPreview src={src} />
      </AttachmentDialogContent>
    </Dialog>
  );
};

const AttachmentThumb: FC = () => {
  const isImage = useAuiState(({ attachment }) => attachment.type === "image");
  const src = useAttachmentSrc();
  return (
    <Avatar className="bg-muted flex size-10 items-center justify-center rounded border text-sm">
      <AvatarFallback delayMs={isImage ? 200 : 0}>
        <FileIcon />
      </AvatarFallback>
      <AvatarImage src={src} />
    </Avatar>
  );
};

const AttachmentUI: FC = () => {
  const canRemove = useAuiState(({ attachment }) => attachment.source !== "message");
  const typeLabel = useAuiState(({ attachment }) => {
    const type = attachment.type;
    switch (type) {
      case "image":
        return "Image";
      case "document":
        return "Document";
      case "file":
        return "File";
      default:
        const _exhaustiveCheck: never = type;
        throw new Error(`Unknown attachment type: ${_exhaustiveCheck}`);
    }
  });
  return (
    <TooltipPrimitive.Provider>
      <Tooltip>
        <AttachmentPrimitive.Root className="relative mt-3">
          <AttachmentPreviewDialog>
            <TooltipTrigger asChild>
              <div className="flex h-12 w-40 items-center justify-center gap-2 rounded-lg border p-1">
                <AttachmentThumb />
                <div className="flex-grow basis-0">
                  <p className="text-muted-foreground line-clamp-1 text-ellipsis break-all text-xs font-bold">
                    <AttachmentPrimitive.Name />
                  </p>
                  <p className="text-muted-foreground text-xs">{typeLabel}</p>
                </div>
              </div>
            </TooltipTrigger>
          </AttachmentPreviewDialog>
          {canRemove && <AttachmentRemove />}
        </AttachmentPrimitive.Root>
        <TooltipContent side="top">
          <AttachmentPrimitive.Name />
        </TooltipContent>
      </Tooltip>
    </TooltipPrimitive.Provider>
  );
};

const AttachmentRemove: FC = () => {
  return (
    <AttachmentPrimitive.Remove asChild>
      <TooltipIconButton
        tooltip="Remove file"
        className="text-muted-foreground [&>svg]:bg-background absolute -right-3 -top-3 size-6 [&>svg]:size-4 [&>svg]:rounded-full"
        side="top"
      >
        <CircleXIcon />
      </TooltipIconButton>
    </AttachmentPrimitive.Remove>
  );
};

export const UserMessageAttachments: FC = () => {
  return (
    <div className="flex w-full flex-row gap-3 col-span-full col-start-1 row-start-1 justify-end">
      <MessagePrimitive.Attachments components={{ Attachment: AttachmentUI }} />
    </div>
  );
};

export const ComposerAttachments: FC = () => {
  return (
    <div className="flex w-full flex-row gap-3 px-1">
      <ComposerPrimitive.Attachments
        components={{ Attachment: AttachmentUI }}
      />
    </div>
  );
};

export const ComposerAddAttachment: FC = () => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <ComposerPrimitive.AddAttachment asChild>
      <TooltipIconButton
        className="my-1 size-9 p-2 rounded-lg transition-all duration-300 hover:bg-muted/80 hover:shadow-sm hover:scale-105 active:scale-95 border border-border/40 hover:border-primary/30"
        tooltip="Add images or files"
        variant="outline"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <PaperclipIcon 
          className={cn(
            "size-4 transition-all duration-300", 
            isHovered ? "text-primary rotate-12" : "text-muted-foreground"
          )} 
        />
      </TooltipIconButton>
    </ComposerPrimitive.AddAttachment>
  );
};

const AttachmentDialogContent: FC<PropsWithChildren> = ({ children }) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content className="aui-dialog-content">
      {children}
    </DialogPrimitive.Content>
  </DialogPortal>
);
