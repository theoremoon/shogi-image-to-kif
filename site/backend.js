'use strict';
(() => {
  let worker, nextId = 0;
  const pending = new Map();
  function getWorker() {
    if (worker) return worker;
    worker = new Worker(new URL('./worker.js', document.baseURI));
    worker.onmessage = ({data}) => {
      if (data.progress) {
        document.dispatchEvent(new CustomEvent('runtime-status', {detail:data.progress}));
        return;
      }
      const call = pending.get(data.id);
      if (!call) return;
      pending.delete(data.id);
      if (data.error) call.reject(new Error(data.error));
      else call.resolve(data.result);
    };
    worker.onerror = event => {
      for (const call of pending.values()) call.reject(new Error(event.message || 'Runtime load failed. Reload to retry.'));
      pending.clear();
      worker.terminate(); worker = null;
    };
    return worker;
  }
  window.shogiBackend = {
    request(path, data) {
      return new Promise((resolve,reject) => {
        const id = ++nextId;
        getWorker().postMessage({id,path,data});
        pending.set(id, {resolve,reject});
      });
    },
    async samples() {
      const response = await fetch(new URL('./samples.json', document.baseURI));
      if (!response.ok) throw new Error('Samples unavailable');
      return response.json();
    },
    sampleUrl(row) {return new URL(row.file, document.baseURI).href;}
  };
})();
