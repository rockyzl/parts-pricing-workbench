/* Same-origin pricing API and memory-only Firebase authentication.
 * Firebase REST contract: https://firebase.google.com/docs/reference/rest/auth
 */
export class ApiError extends Error {
  constructor(status, payload = {}) {
    const error = payload.error || {};
    super(error.code || 'REQUEST_FAILED');
    this.name = 'ApiError'; this.status = status; this.code = error.code || 'REQUEST_FAILED';
    this.fields = error.fields; this.requestId = error.request_id; this.currentRevision = error.current_revision;
  }
}
export class OperationCancelled extends Error {
  constructor() { super('Operation belongs to an earlier identity session'); this.name = 'OperationCancelled'; }
}
export class Session {
  constructor(config, fetcher = globalThis.fetch.bind(globalThis)) {
    this.config = config; this.fetcher = fetcher; this.clear();
  }
  clear() { this.idToken = null; this.refreshToken = null; this.uid = null; this.expiresAt = 0; this.generation = (this.generation || 0) + 1; this.refreshing = null; }
  async signIn(email, password) {
    if (!this.config?.api_key) throw new ApiError(503, {error:{code:'SIGN_IN_UNAVAILABLE'}});
    const generation = ++this.generation; this.refreshing = null;
    const response = await this.fetcher(`https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${encodeURIComponent(this.config.api_key)}`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({email,password,returnSecureToken:true}), credentials:'omit'
    });
    const result = await response.json();
    if (!response.ok) throw new ApiError(response.status, {error:{code:'SIGN_IN_FAILED'}});
    if (generation !== this.generation) throw new OperationCancelled();
    this.idToken = result.idToken; this.refreshToken = result.refreshToken; this.uid = result.localId;
    this.expiresAt = Date.now() + Number(result.expiresIn) * 1000;
  }
  async token() {
    if (!this.idToken) throw new ApiError(401, {error:{code:'SIGN_IN_REQUIRED'}});
    if (Date.now() < this.expiresAt - 90000) return this.idToken;
    if (!this.refreshing) {
      const task = this.refresh().finally(() => { if (this.refreshing === task) this.refreshing = null; });
      this.refreshing = task;
    }
    return this.refreshing;
  }
  async refresh() {
    const generation = this.generation;
    let response;
    try {
      response = await this.fetcher(`https://securetoken.googleapis.com/v1/token?key=${encodeURIComponent(this.config.api_key)}`, {
        method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:new URLSearchParams({grant_type:'refresh_token',refresh_token:this.refreshToken}), credentials:'omit'
      });
    } catch { throw new ApiError(503, {error:{code:'AUTH_NETWORK_UNAVAILABLE'}}); }
    const result = await response.json();
    if (!response.ok || generation !== this.generation) { if (generation === this.generation) this.clear(); throw new ApiError(401, {error:{code:'SESSION_EXPIRED'}}); }
    this.idToken = result.id_token; this.refreshToken = result.refresh_token;
    this.expiresAt = Date.now() + Number(result.expires_in) * 1000;
    return this.idToken;
  }
}
export class ApiClient {
  constructor(session, {fetcher = globalThis.fetch.bind(globalThis), storage = globalThis.sessionStorage} = {}) {
    this.session = session; this.fetcher = fetcher; this.storage = storage; this.pendingKeys = new Map();
    this.generation = 0; this.controllers = new Set();
  }
  assertCurrent(generation) { if (generation !== this.generation) throw new OperationCancelled(); }
  invalidate({clearPending = false} = {}) {
    this.generation++;
    for (const controller of this.controllers) controller.abort();
    this.controllers.clear();
    if (clearPending) {
      const keys = new Set(this.pendingKeys.keys());
      try { for (let i=0;i<this.storage?.length;i++) { const key=this.storage.key(i); if (key?.startsWith('pricing-request:')) keys.add(key); } } catch {}
      for (const key of keys) { try { this.storage?.removeItem(key); } catch {} }
      this.pendingKeys.clear();
    }
  }
  scoped() {
    const generation = this.generation;
    return {
      request:(path, options={}) => this.request(path,{...options,generation}),
      all:(path, options={}) => this.all(path,{...options,generation}),
    };
  }
  async request(path, {method = 'GET', body, etag, publicAccess = false, raw = false, download = false, generation = this.generation} = {}) {
    this.assertCurrent(generation);
    if (!path.startsWith('/api/v1/')) throw new Error('Only same-origin pricing routes are allowed');
    const controller = new AbortController(); this.controllers.add(controller);
    try {
      const headers = {Accept:download ? 'text/csv' : 'application/json'};
      const actor = this.session?.uid || 'anonymous';
      if (!publicAccess) { const token = await this.session.token(); this.assertCurrent(generation); headers.Authorization = `Bearer ${token}`; }
      if (etag) headers['If-Match'] = etag;
      const encoded = body === undefined ? undefined : raw ? body : JSON.stringify(body);
      let pending;
      if (method !== 'GET') {
        headers['Content-Type'] = raw ? 'text/csv' : 'application/json';
        const bytes = new TextEncoder().encode(`${actor}\n${method}\n${path}\n${encoded || ''}`);
        const digest = await crypto.subtle.digest('SHA-256', bytes);
        this.assertCurrent(generation);
        pending = 'pricing-request:' + Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2,'0')).join('');
        let key = this.pendingKeys.get(pending);
        try { key ||= this.storage?.getItem(pending); } catch {}
        key ||= crypto.randomUUID(); this.pendingKeys.set(pending,key);
        try { this.storage?.setItem(pending,key); } catch {}
        headers['Idempotency-Key'] = key;
      }
      this.assertCurrent(generation);
      let response;
      try { response = await this.fetcher(path, {method, headers, body:encoded, credentials:'same-origin',cache:'no-store',signal:controller.signal}); }
      catch { this.assertCurrent(generation); throw new ApiError(0, {error:{code:'CONNECTION_LOST'}}); }
      this.assertCurrent(generation);
      if (!response.ok) {
        let error; try { error = await response.json(); } catch { this.assertCurrent(generation); error = {error:{code:'SERVICE_UNAVAILABLE'}}; }
        this.assertCurrent(generation);
        throw new ApiError(response.status,error);
      }
      // A successful status is not an accepted response until its full body is read.
      // An interrupted body keeps the original mutation key for a deliberate retry.
      let data;
      try { data = response.status === 204 ? null : download ? await response.blob() : await response.json(); }
      catch { this.assertCurrent(generation); throw new ApiError(0,{error:{code:'RESPONSE_INTERRUPTED'}}); }
      this.assertCurrent(generation);
      if (pending) { this.pendingKeys.delete(pending); try { this.storage?.removeItem(pending); } catch {} }
      return {data,etag:response.headers.get('ETag') || data?.etag};
    } finally { this.controllers.delete(controller); }
  }
  async all(path, options = {}) {
    const generation = options.generation ?? this.generation;
    let items = [], cursor = null, seen = new Set();
    do {
      this.assertCurrent(generation);
      const separator = path.includes('?') ? '&' : '?';
      const {data} = await this.request(`${path}${separator}limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, {...options,generation});
      this.assertCurrent(generation);
      items.push(...(data.items || [])); cursor = data.next_cursor;
      if (cursor && seen.has(cursor)) throw new ApiError(500,{error:{code:'INVALID_PAGE_CURSOR'}});
      seen.add(cursor);
    } while (cursor);
    return items;
  }
}
