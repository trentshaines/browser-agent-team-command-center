import { getContext } from 'svelte';
import { useConvexClient, useQuery as _useQuery } from 'convex-svelte';
import type { FunctionReference, FunctionArgs, FunctionReturnType } from 'convex/server';
import type { ConvexClient } from 'convex/browser';

const CONTEXT_KEY = '$$_convexClient';

/**
 * Returns true if Convex has been initialized via setupConvex().
 */
export function isConvexConfigured(): boolean {
  try {
    return getContext(CONTEXT_KEY) != null;
  } catch {
    return false;
  }
}

/**
 * Safe version of useConvexClient — returns null if Convex isn't configured.
 */
export function useSafeConvexClient(): ConvexClient | null {
  try {
    const client = getContext<ConvexClient | undefined>(CONTEXT_KEY);
    return client ?? null;
  } catch {
    return null;
  }
}

type UseQueryReturn<Query extends FunctionReference<'query'>> = {
  data: FunctionReturnType<Query> | undefined;
  error: Error | undefined;
  isLoading: boolean;
  isStale: boolean;
};

const EMPTY_QUERY_RESULT: UseQueryReturn<any> = {
  data: undefined,
  error: undefined,
  isLoading: false,
  isStale: false,
};

/**
 * Safe version of useQuery — returns an inert result if Convex isn't configured.
 */
export function useSafeQuery<Query extends FunctionReference<'query'>>(
  query: Query,
  args?: FunctionArgs<Query> | 'skip' | (() => FunctionArgs<Query> | 'skip'),
): UseQueryReturn<Query> {
  if (!isConvexConfigured()) {
    return EMPTY_QUERY_RESULT;
  }
  return _useQuery(query, args) as UseQueryReturn<Query>;
}
