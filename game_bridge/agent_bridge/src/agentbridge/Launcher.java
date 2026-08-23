package agentbridge;

import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.IllegalClassFormatException;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;

import org.objectweb.asm.ClassReader;
import org.objectweb.asm.ClassVisitor;
import org.objectweb.asm.ClassWriter;
import org.objectweb.asm.MethodVisitor;
import org.objectweb.asm.Opcodes;

import age.of.civilizations2.jakowski.lukasz.AgentBridge;

/**
 * Javaagent premain: starts AgentBridge HTTP server and injects
 * AgentBridge.tick() at the top of AoCGame.render() so every engine command
 * executes on the GL thread.
 */
public class Launcher {
    public static void premain(String args, Instrumentation inst) throws Exception {
        int port = Integer.getInteger("aoc2.bridge.port", 9110);
        AgentBridge.start(port);
        inst.addTransformer(new RenderHookTransformer(), false);
    }

    private static class RenderHookTransformer implements ClassFileTransformer {
        @Override
        public byte[] transform(ClassLoader loader, String className, Class<?> classBeingRedefined,
                                ProtectionDomain protectionDomain, byte[] classfileBuffer)
                throws IllegalClassFormatException {
            if (className == null || !className.equals("age/of/civilizations2/jakowski/lukasz/AoCGame")) {
                return null;
            }
            try {
                ClassReader cr = new ClassReader(classfileBuffer);
                ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
                ClassVisitor cv = new ClassVisitor(Opcodes.ASM9, cw) {
                    @Override
                    public MethodVisitor visitMethod(int access, String name, String desc,
                                                     String signature, String[] exceptions) {
                        MethodVisitor mv = super.visitMethod(access, name, desc, signature, exceptions);
                        if (!name.equals("render") && !name.equals("draw")) {
                            return mv;
                        }
                        return new MethodVisitor(Opcodes.ASM9, mv) {
                            @Override
                            public void visitCode() {
                                super.visitCode();
                                mv.visitMethodInsn(Opcodes.INVOKESTATIC,
                                        "age/of/civilizations2/jakowski/lukasz/AgentBridge", "tick", "()V", false);
                            }
                        };
                    }
                };
                cr.accept(cv, 0);
                return cw.toByteArray();
            } catch (Throwable t) {
                return null; // leave class unchanged on any failure
            }
        }
    }
}
