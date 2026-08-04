import * as React from 'react';
import { renderFormComponent } from '@/components/ui/form/index';
import { createPortal } from 'react-dom';
import * as ReactDOM from 'react-dom/client';
import {
  useForm as useReactHookForm,
  FormProvider as ReactHookFormProvider,
  Controller,
} from 'react-hook-form';
import type {
  SubmitHandler,
  FieldValues,
  DefaultValues,
  RegisterOptions,
  FieldErrors,
  Path,
  PathValue,
  UseFormReturn,
} from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import {
  useFormField,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
  FormField,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { useTranslation } from '@/i18n';

// Form field type definition
export type FormFieldType<T extends string = string> = 
  | 'text'
  | 'password'
  | 'number'
  | 'textarea'
  | 'select'
  | 'checkbox'
  | 'switch'
  | 'custom'
  | T;

// Select option type
export interface SelectOption {
  label: React.ReactNode;
  value: string;
}

// Form field configuration
export interface FormFieldConfig<T extends FieldValues = any> {
  name: Path<T>;
  label?: React.ReactNode;
  type: FormFieldType;
  placeholder?: string;
  description?: React.ReactNode;
  defaultValue?: any;
  options?: SelectOption[];
  validation?: RegisterOptions;
  className?: string;
  disabled?: boolean;
  hidden?: boolean;
  render?: (field: any, error?: FieldErrors) => React.ReactNode;
}

// Form configuration
export interface FormConfig<T extends FieldValues = any> {
  fields: FormFieldConfig<T>[];
  defaultValues?: DefaultValues<T>;
  schema?: z.ZodType<any, any>;
  onSubmit?: SubmitHandler<T>;
  submitText?: React.ReactNode;
  cancelText?: React.ReactNode;
  onCancel?: () => void;
  showActions?: boolean;
  className?: string;
  fieldClassName?: string;
}

// Form instance interface
export interface FormInstance<T extends FieldValues = any> {
  submit: () => Promise<T | undefined>;
  reset: (values?: DefaultValues<T>) => void;
  setValue: <K extends Path<T>>(name: K, value: PathValue<T, K>) => void;
  getValues: () => T;
  setError: (name: Path<T>, error: { type: string; message: string }) => void;
  clearErrors: (name?: Path<T>) => void;
  formState: {
    errors: FieldErrors<T>;
    isDirty: boolean;
    isSubmitting: boolean;
    isValid: boolean;
  };
}

// Return value of createForm
export interface CreateFormResult<T extends FieldValues = any> {
  FormComponent: React.FC;
  formInstance: FormInstance<T>;
}

// Form context
interface FormContextValue<T extends FieldValues = any> {
  config: FormConfig<T>;
  formInstance: FormInstance<T>;
}

const FormContext = React.createContext<FormContextValue | null>(null);

// Hook for consuming the form context
export const useFormContext = <T extends FieldValues = any>() => {
  const context = React.useContext(FormContext) as FormContextValue<T> | null;
  if (!context) {
    throw new Error('useFormContext must be used within a FormProvider');
  }
  return context;
};



// Render a form field
const renderFormField = <T extends FieldValues>(
  field: FormFieldConfig<T>,
  errors: FieldErrors<T>
) => {
  if (field.hidden) return null;

  // Use the custom render function when one is provided.
  if (field.type === 'custom' && field.render) {
    return field.render(field, errors);
  }

  return (
    <FormField
      key={field.name.toString()}
      name={field.name}
      render={({ field: formField }) => (
        <FormItem className={field.className}>
          {field.label && <FormLabel>{field.label}</FormLabel>}
          
          <FormControl>
            {/* Render the form component through the component registry */}
            {renderFormComponent(field.type, {
              ...formField,
            }) || (
              // Default rendering, used as a fallback
              <>
                {field.type === 'text' && (
                  <Input
                    {...formField}
                    type="text"
                    placeholder={field.placeholder}
                    disabled={field.disabled}
                  />
                )}
                
                {field.type === 'password' && (
                  <Input
                    {...formField}
                    type="password"
                    placeholder={field.placeholder}
                    disabled={field.disabled}
                  />
                )}
                
                {field.type === 'number' && (
                  <Input
                    {...formField}
                    type="number"
                    placeholder={field.placeholder}
                    disabled={field.disabled}
                    onChange={(e) => {
                      const value = e.target.value === '' ? '' : Number(e.target.value);
                      formField.onChange(value);
                    }}
                  />
                )}
                
                {field.type === 'textarea' && (
                  <Textarea
                    {...formField}
                    placeholder={field.placeholder}
                    disabled={field.disabled}
                  />
                )}
                
                {field.type === 'select' && field.options && (
                  <Select
                    onValueChange={formField.onChange}
                    defaultValue={formField.value}
                    value={formField.value}
                    disabled={field.disabled}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={field.placeholder} />
                    </SelectTrigger>
                    <SelectContent>
                      {field.options.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                
                {field.type === 'checkbox' && (
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      checked={formField.value}
                      onCheckedChange={formField.onChange}
                      disabled={field.disabled}
                    />
                    {field.label && <span>{field.label}</span>}
                  </div>
                )}
                
                {field.type === 'switch' && (
                  <div className="flex items-center space-x-2">
                    <Switch
                      checked={formField.value}
                      onCheckedChange={formField.onChange}
                      disabled={field.disabled}
                    />
                    {field.label && <span>{field.label}</span>}
                  </div>
                )}
              </>
            )}
          </FormControl>
          
          {field.description && <FormDescription>{field.description}</FormDescription>}
          <FormMessage />
        </FormItem>
      )}
    />
  );
};

// Create the form component
export const createForm = <T extends FieldValues>(
  config: FormConfig<T>
): CreateFormResult<T> => {
  // Create the form instance
  const methods = useReactHookForm<T>({
    defaultValues: config.defaultValues,
    resolver: config.schema ? zodResolver(config.schema) : undefined,
  });

  // Build the form instance interface
  const formInstance: FormInstance<T> = {
    submit: async () => {
      try {
        const onSubmitHandler = config.onSubmit || (() => {});
        return await new Promise<T | undefined>((resolve) => {
          methods.handleSubmit((data: T) => {
            onSubmitHandler(data);
            resolve(data);
          }, () => resolve(undefined))();
        });
      } catch (error) {
        console.error('Form submission error:', error);
        return undefined;
      }
    },
    reset: methods.reset,
    setValue: methods.setValue,
    getValues: methods.getValues,
    setError: methods.setError,
    clearErrors: methods.clearErrors,
    formState: methods.formState,
  };

  // Form component
  const FormComponent: React.FC = () => {
    const { t } = useTranslation();
    const handleSubmit = methods.handleSubmit(config.onSubmit || (() => {}));

    return (
      <ReactHookFormProvider {...methods}>
        <form onSubmit={handleSubmit} className={config.className}>
          <div className={config.fieldClassName || 'space-y-4'}>
            {config.fields.map((field) => !field.hidden && renderFormField(field, methods.formState.errors))}
          </div>

          {config.showActions !== false && (
            <div className="flex justify-end space-x-2 mt-6">
              {config.onCancel && (
                <Button type="button" variant="outline" onClick={config.onCancel}>
                  {config.cancelText || t('common.operation.cancel')}
                </Button>
              )}
              <Button type="submit">
                {config.submitText || t('common.operation.submit')}
              </Button>
            </div>
          )}
        </form>
      </ReactHookFormProvider>
    );
  };

  return { FormComponent, formInstance };
};

// Form provider component
export interface FormProviderProps {
  children: React.ReactNode;
}

// Form provider context
export const HookFormProvider: React.FC<FormProviderProps> = ({ children }) => {
  // Build a default form context
  const defaultFormContext = React.useMemo<FormContextValue>(() => {
    const defaultConfig: FormConfig = {
      fields: [],
    };
    
    const { FormComponent, formInstance } = createForm(defaultConfig);
    
    return {
      config: defaultConfig,
      formInstance,
    };
  }, []);

  return (
    <FormContext.Provider value={defaultFormContext}>
      {children}
    </FormContext.Provider>
  );
};

// Hook for accessing the current form
export const useHookForm = <T extends FieldValues>(): FormInstance<T> => {
  const { formInstance } = useFormContext<T>();
  return formInstance;
};

// Create a standalone form instance
export const createHookForm = <T extends FieldValues>(): {
  create: (config: FormConfig<T>) => React.ReactNode;
} => {
  return {
    create: (config: FormConfig<T>) => {
      const { FormComponent, formInstance } = createForm<T>(config);
      
      // Wrapper component that provides the form context
      const WrappedFormComponent: React.FC = () => {
        const formContext = React.useMemo<FormContextValue<T>>(() => {
          return {
            config,
            formInstance,
          };
        }, []);

        return (
          <FormContext.Provider value={formContext}>
            <FormComponent />
          </FormContext.Provider>
        );
      };

      return <WrappedFormComponent />;
    },
  };
};
