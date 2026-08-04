import { useQuery as useReactQuery } from '@tanstack/react-query'
import type { UseQueryOptions, QueryKey, UseMutationOptions } from '@tanstack/react-query'
import { useMutation as useReactMutation } from '@tanstack/react-query'

interface UseMutationParams<TData = any, TError = any, TVariables = any> {
  mutationKey: QueryKey
  mutationFn: (variables: TVariables) => Promise<TData>
  onSuccess?: (data: TData) => void
  onError?: (error: TError) => void
  options?: Omit<UseMutationOptions<TData, TError, TVariables>, 'mutationKey' | 'mutationFn' | 'onSuccess' | 'onError'>
  onMutate?: (variables: TVariables) => void
}

interface UseQueryParams<TData = any, TError = any> {
  queryKey: QueryKey
  queryFn: () => Promise<TData>
  options?: Omit<UseQueryOptions<TData, TError>, 'queryKey' | 'queryFn'>
}

export function useQuery<TData = any, TError = any>({
  queryKey,
  queryFn,
  options = {},
}: UseQueryParams<TData, TError>) {
  return useReactQuery<TData, TError>({
    queryKey,
    queryFn,
    ...options,
  })
} 

// Thin wrapper around useMutation
export function useMutation<TData = any, TError = any, TVariables = any>({
  mutationKey,
  mutationFn,
  options = {},
  onSuccess,
  onError,
  onMutate,
}: UseMutationParams<TData, TError, TVariables>) {
  return useReactMutation<TData, TError, TVariables>({
    mutationKey,
    mutationFn,
    onSuccess,
    onError,
    onMutate,
    ...options,
  })
}
