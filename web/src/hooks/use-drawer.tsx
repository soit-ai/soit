import * as React from 'react';
import { createPortal } from 'react-dom';
import * as ReactDOM from 'react-dom/client';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerFooter,
  DrawerClose,
} from '@/components/ui/drawer';

type DrawerSize = 'default' | 'sm' | 'lg' | 'xl' | 'full';
type DrawerDirection = 'top' | 'bottom' | 'left' | 'right';

interface DrawerOptions {
  title?: React.ReactNode;
  description?: React.ReactNode;
  direction?: DrawerDirection;
  size?: DrawerSize;
  showClose?: boolean;
  footer?: React.ReactNode;
  onOpenChange?: (open: boolean) => void;
  onClose?: () => void;
  className?: string;
  contentClassName?: string;
  headerClassName?: string;
  footerClassName?: string;
}

interface DrawerInstance {
  open: (content: React.ReactNode, options?: DrawerOptions) => void;
  close: () => void;
  update: (content: React.ReactNode, options?: DrawerOptions) => void;
}

const DrawerContext = React.createContext<DrawerInstance | null>(null);

export const useDrawer = (): DrawerInstance => {
  const context = React.useContext(DrawerContext);
  if (!context) {
    throw new Error('useDrawer must be used within a DrawerProvider');
  }
  return context;
};

interface DrawerProviderProps {
  children: React.ReactNode;
  handleOnly?: boolean;
}

interface DrawerContentState {
  id: string;
  content: React.ReactNode;
  options: DrawerOptions;
}

export const DrawerProvider: React.FC<DrawerProviderProps> = ({ children, handleOnly = true }) => {
  // 使用数组存储多个drawer状态
  const [drawers, setDrawers] = React.useState<DrawerContentState[]>([]);
  const [portalContainer, setPortalContainer] = React.useState<HTMLElement | null>(null);

  React.useEffect(() => {
    // 创建一个新的div元素作为portal容器
    const div = document.createElement('div');
    document.body.appendChild(div);
    setPortalContainer(div);

    // 组件卸载时移除portal容器
    return () => {
      document.body.removeChild(div);
    };
  }, []);

  const handleOpenChange = React.useCallback(
    (value: boolean, drawerId: string) => {
      if (!value) {
        // 关闭特定的drawer
        const drawerToClose = drawers.find(d => d.id === drawerId);
        if (drawerToClose?.options.onClose) {
          drawerToClose.options.onClose();
        }
        if (drawerToClose?.options.onOpenChange) {
          drawerToClose.options.onOpenChange(value);
        }
        // 从数组中移除该drawer
        setDrawers(prev => prev.filter(d => d.id !== drawerId));
      }
    },
    [drawers]
  );

  const api = React.useMemo<DrawerInstance>(
    () => ({
      open: (content, options = {}) => {
        // 生成唯一ID
        const id = `drawer-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        // 添加新的drawer到数组
        setDrawers(prev => [...prev, { id, content, options }]);
      },
      close: () => {
        // 关闭最后一个drawer
        if (drawers.length > 0) {
          const lastDrawer = drawers[drawers.length - 1];
          handleOpenChange(false, lastDrawer.id);
        }
      },
      update: (content, options = {}) => {
        // 更新最后一个drawer
        if (drawers.length > 0) {
          setDrawers(prev => {
            const newDrawers = [...prev];
            const lastIndex = newDrawers.length - 1;
            newDrawers[lastIndex] = {
              ...newDrawers[lastIndex],
              content,
              options: { ...newDrawers[lastIndex].options, ...options },
            };
            return newDrawers;
          });
        }
      },
    }),
    [drawers, handleOpenChange]
  );

  const getSizeClassName = (size?: DrawerSize): string => {
    switch (size) {
      case 'sm':
        return 'sm:max-w-sm';
      case 'lg':
        return 'sm:max-w-lg';
      case 'xl':
        return 'sm:max-w-xl';
      case 'full':
        return 'sm:max-w-full';
      default:
        return 'sm:max-w-[600px]';
    }
  };

  return (
    <DrawerContext.Provider value={api}>
      {children}
      {portalContainer && drawers.map((drawer) => createPortal(
        <Drawer 
          key={drawer.id}
          open={true} 
          handleOnly={handleOnly}
          onOpenChange={(value) => handleOpenChange(value, drawer.id)} 
          direction={drawer.options.direction || 'right'}
        >
          <DrawerContent className={`${drawer.options.contentClassName || ''} !w-[500px] !max-w-[500px]`}>
            {(drawer.options.title || drawer.options.description) && (
              <DrawerHeader className={drawer.options.headerClassName}>
                {drawer.options.title && <DrawerTitle>{drawer.options.title}</DrawerTitle>}
                {drawer.options.description && (
                  <DrawerDescription>{drawer.options.description}</DrawerDescription>
                )}
                {drawer.options.showClose && <DrawerClose />}
              </DrawerHeader>
            )}
            <div className="p-4 flex-1 overflow-auto">{drawer.content}</div>
            {drawer.options.footer && (
              <DrawerFooter className={drawer.options.footerClassName}>
                {drawer.options.footer}
              </DrawerFooter>
            )}
          </DrawerContent>
        </Drawer>,
        portalContainer
      ))}
    </DrawerContext.Provider>
  );
};

// 创建一个独立的drawer实例，不需要使用Provider
export const createDrawer = (): DrawerInstance => {
  let drawerRoot: HTMLDivElement | null = null;
  let drawerInstance: DrawerInstance | null = null;

  const DrawerComponent: React.FC<{ content: React.ReactNode; options?: DrawerOptions }> = ({ 
    content, 
    options = {} 
  }) => {
    const [isOpen, setIsOpen] = React.useState(true);

    const handleOpenChange = (open: boolean) => {
      setIsOpen(open);
      if (!open) {
        if (options.onClose) {
          options.onClose();
        }
        if (options.onOpenChange) {
          options.onOpenChange(open);
        }
        // 关闭后移除DOM节点
        setTimeout(() => {
          try {
            if (drawerRoot && document.body.contains(drawerRoot)) {
              document.body.removeChild(drawerRoot);
            }
          } catch (error) {
            console.warn('移除抽屉DOM节点时出错:', error);
          } finally {
            drawerRoot = null;
          }
        }, 300); // 等待动画完成
      }
    };

    return (
      <Drawer open={isOpen} onOpenChange={handleOpenChange} direction={options.direction || 'right'}>
        <DrawerContent className={`${options.contentClassName || ''} !w-[500px] !max-w-[500px]`}>
          {(options.title || options.description) && (
            <DrawerHeader className={options.headerClassName}>
              {options.title && <DrawerTitle>{options.title}</DrawerTitle>}
              {options.description && <DrawerDescription>{options.description}</DrawerDescription>}
              {options.showClose && <DrawerClose />}
            </DrawerHeader>
          )}
          <div className="p-4 flex-1 overflow-auto">{content}</div>
          {options.footer && (
            <DrawerFooter className={options.footerClassName}>{options.footer}</DrawerFooter>
          )}
        </DrawerContent>
      </Drawer>
    );
  };

  const render = (content: React.ReactNode, options?: DrawerOptions) => {
    // 如果已存在，先移除旧的
    try {
      if (drawerRoot && document.body.contains(drawerRoot)) {
        document.body.removeChild(drawerRoot);
      }
    } catch (error) {
      console.warn('移除旧抽屉DOM节点时出错:', error);
    }

    // 创建新的容器
    drawerRoot = document.createElement('div');
    document.body.appendChild(drawerRoot);

    // 渲染抽屉到容器
    const root = ReactDOM.createRoot(drawerRoot);
    root.render(<DrawerComponent content={content} options={options} />);
  };

  drawerInstance = {
    open: (content, options) => {
      render(content, options);
    },
    close: () => {
      if (drawerRoot) {
        const event = new Event('click', { bubbles: true });
        const closeButton = drawerRoot.querySelector('[data-slot="drawer-close"]');
        if (closeButton) {
          closeButton.dispatchEvent(event);
        }
      }
    },
    update: (content, options) => {
      render(content, options);
    },
  };

  return drawerInstance;
};
