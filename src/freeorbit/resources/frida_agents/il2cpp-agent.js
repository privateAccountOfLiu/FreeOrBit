// Entry point for frida-compile to build il2cpp-bridge agent
try {
  const il2cpp = require("frida-il2cpp-bridge");

  // Expose all bridge functionality as RPC exports
  rpc.exports = {
    ...il2cpp.exports,
    dump: il2cpp.dump,
    dumpTree: il2cpp.dumpTree,
    installExceptionListener: il2cpp.installExceptionListener,
  };

  console.log("[il2cpp-bridge] initialized successfully");
} catch (e) {
  console.error("[il2cpp-bridge] initialization failed: " + e.message);
  console.error("[il2cpp-bridge] This target may not be a Unity IL2CPP application.");
  console.error("[il2cpp-bridge] The bridge is disabled; your custom script will still run.");
}
