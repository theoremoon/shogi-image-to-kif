'use strict';
const CDN = 'https://cdn.jsdelivr.net/pyodide/v0.28.1/full/';
let ready;
async function runtime() {
  if (!ready) ready = initialize().catch(error => {ready = null; throw error;});
  return ready;
}
async function initialize() {
  self.postMessage({progress:'Loading… (first run)'});
  importScripts(CDN + 'pyodide.js');
  const py = await loadPyodide({indexURL:CDN});
  await py.loadPackage(['numpy','Pillow','opencv-python']);
  const response = await fetch(new URL('./runtime.zip', self.location.href));
  if (!response.ok) throw new Error('Runtime download failed');
  py.unpackArchive(await response.arrayBuffer(), 'zip', {extractDir:'/app'});
  py.runPython("import sys, os; sys.path.insert(0, '/app'); os.environ['SHOGI_WARS_TEMPLATES']='/app/shogi_image_to_kif/assets/wars-templates.npz'");
  py.runPython('from shogi_image_to_kif.browser import dispatch');
  self.postMessage({progress:'Reading…'});
  return py;
}
// Serialize requests so their Python globals cannot overwrite each other.
let queue = Promise.resolve();
self.onmessage = ({data}) => {
  queue = queue.then(async () => {
    try {
      const py = await runtime();
      py.globals.set('_request', JSON.stringify({path:data.path,data:data.data}));
      const result = JSON.parse(py.runPython('dispatch(_request)'));
      self.postMessage({id:data.id,result});
    } catch (error) {
      self.postMessage({id:data.id,error:error.message});
    }
  });
};
