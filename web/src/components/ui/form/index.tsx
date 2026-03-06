import * as React from 'react';
import type { FormFieldType, SelectOption } from '@/hooks/use-form';
import { ModelOption } from './model-option';
import { SelectModel } from './select-model';

// Form component registry interface.
interface FormComponentRegistry {
  [key: string]: React.ComponentType<any>;
}

// Form renderer interface.
interface FormComponentRenderer {
  (props: any): React.ReactNode;
}

// Global component registry.
const componentRegistry: FormComponentRegistry = {};

// Global renderer registry.
const rendererRegistry: Record<string, FormComponentRenderer> = {};

export const autoRegisterFormComponents = () => {
  registerFormComponent('select-model', SelectModel);
  registerFormComponent('model-option', ModelOption);
};

autoRegisterFormComponents();

/**
 * Register a form component.
 * @param type Component type
 * @param component Component instance
 */
export function registerFormComponent<T, U extends string = string>(type: FormFieldType<U>, component: React.ComponentType<T>) {
  componentRegistry[type as string] = component as React.ComponentType<any>;
}

/**
 * Register a form renderer.
 * @param type Component type
 * @param renderer Render function
 */
export function registerFormRenderer<T extends string = string>(type: FormFieldType<T>, renderer: FormComponentRenderer) {
  rendererRegistry[type as string] = renderer;
}

/**
 * Get a registered form component.
 * @param type Component type
 */
export function getFormComponent<T extends string = string>(type: FormFieldType<T>): React.ComponentType<any> | undefined {
  return componentRegistry[type as string];
}

/**
 * Get a registered form renderer.
 * @param type Component type
 */
export function getFormRenderer<T extends string = string>(type: FormFieldType<T>): FormComponentRenderer | undefined {
  return rendererRegistry[type as string];
}

/**
 * Render a form component.
 * @param type Component type
 * @param props Component props
 */
export function renderFormComponent<T extends string = string>(type: FormFieldType<T>, props: any): React.ReactNode {
  // Try the renderer first.
  const renderer = getFormRenderer(type as FormFieldType);
  if (renderer) {
    return renderer(props);
  }
  
  // Fall back to registered components.
  const Component = getFormComponent(type as FormFieldType);
  if (Component) {
    return <Component {...props} />;
  }

  // Log warning and return null.
  console.warn(`No form component or renderer registered for type: ${type}`);
  return null;
}
