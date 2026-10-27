import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';

// Fetches `path` with `params` and re-fetches whenever they change. Stale responses are ignored.
export function useApi(path, params = {}, { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, loading: enabled, error: null });
  const key = JSON.stringify([path, params]);
  const seq = useRef(0);

  const load = useCallback(() => {
    if (!enabled) return;
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    api
      .get(path, params)
      .then((data) => id === seq.current && setState({ data, loading: false, error: null }))
      .catch((error) => id === seq.current && setState((s) => ({ ...s, loading: false, error })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);

  useEffect(load, [load]);
  return { ...state, reload: load };
}

// Debounces a rapidly changing value (sliders) before it triggers a request.
export function useDebounced(value, delay = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}
