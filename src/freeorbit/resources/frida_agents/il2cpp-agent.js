// Entry point for frida-compile to build il2cpp-bridge agent
const il2cpp = require("frida-il2cpp-bridge");

// Expose all bridge functionality as RPC exports
rpc.exports = {
  ...il2cpp.exports,
  dump: il2cpp.dump,
  dumpTree: il2cpp.dumpTree,
  installExceptionListener: il2cpp.installExceptionListener,
};
