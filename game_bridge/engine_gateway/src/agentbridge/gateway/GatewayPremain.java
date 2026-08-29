package agentbridge.gateway;

/**
 * Bootstrap hook ONLY (no ASM, no ClassFileTransformer, no engine modification).
 *
 * WHY: pure classpath load has no code path that can call EngineGateway.start()
 * (the game main is the engine's DesktopLauncher). JVM calls premain(String)
 * before main, which is the standard "library agent" pattern: the HTTP server
 * comes up instantly; the GL pump loop waits until Gdx.app is non-null.
 */
public final class GatewayPremain {

    private GatewayPremain() {
    }

    public static void premain(String args) {
        try {
            EngineGateway.start();
        } catch (Throwable t) {
            System.err.println("[EngineGateway] bootstrap failed: " + t);
        }
    }
}
