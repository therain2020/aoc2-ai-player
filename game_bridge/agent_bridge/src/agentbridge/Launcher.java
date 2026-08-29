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
    static void log(String s) {
        try {
            java.io.FileWriter fw = new java.io.FileWriter("bridge_diag.log", true);
            fw.write(System.currentTimeMillis() + " " + s + "\n");
            fw.close();
        } catch (Throwable ignored) {
        }
    }

    public static void premain(String args, Instrumentation inst) throws Exception {
        log("premain start");
        int port = Integer.getInteger("aoc2.bridge.port", 9110);
        AgentBridge.start(port);
        inst.addTransformer(new RenderHookTransformer(), false);
        log("transformer added");
    }

    private static class RenderHookTransformer implements ClassFileTransformer {
        @Override
        public byte[] transform(ClassLoader loader, String className, Class<?> classBeingRedefined,
                                ProtectionDomain protectionDomain, byte[] classfileBuffer)
                throws IllegalClassFormatException {
            if (className == null) {
                return null;
            }
            if (className.startsWith("age/of/civilizations2")) {
                Launcher.log("transform hit: " + className);
            }
            if (className.equals("age/of/civilizations2/jakowski/lukasz/AoCGame")) {
                try {
                    ClassReader cr = new ClassReader(classfileBuffer);
                    ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
                    ClassVisitor cv = new ClassVisitor(Opcodes.ASM9, cw) {
                        @Override
                        public MethodVisitor visitMethod(int access, String name, String desc,
                                                         String signature, String[] exceptions) {
                            MethodVisitor mv = super.visitMethod(access, name, desc, signature, exceptions);
                            // FR-006: hotkeys (Insert/PageUp/PageDown/END) removed — only tick + HUD draw stay
                            boolean isTick = name.equals("render") || name.equals("draw");
                            if (!isTick) {
                                return mv;
                            }
                            return new MethodVisitor(Opcodes.ASM9, mv) {
                                @Override
                                public void visitCode() {
                                    super.visitCode();
                                    mv.visitMethodInsn(Opcodes.INVOKESTATIC,
                                            "age/of/civilizations2/jakowski/lukasz/AgentBridge", "tick", "()V", false);
                                }

                                @Override
                                public void visitMethodInsn(int opcode, String owner, String mname,
                                                             String mdesc, boolean itf) {
                                    super.visitMethodInsn(opcode, owner, mname, mdesc, itf);
                                    // draw HUD right after the map-detail draw call (inside AoCGame.render,
                                    // same SpriteBatch is active — safe class-level injection)
                                    if (isTick && owner.equals("age/of/civilizations2/jakowski/lukasz/Game_Render")
                                            && mname.equals("drawMapDetails")) {
                                        mv.visitVarInsn(Opcodes.ALOAD, 0);
                                        mv.visitFieldInsn(Opcodes.GETFIELD,
                                                "age/of/civilizations2/jakowski/lukasz/AoCGame", "oSB",
                                                "Lcom/badlogic/gdx/graphics/g2d/SpriteBatch;");
                                        mv.visitMethodInsn(Opcodes.INVOKESTATIC,
                                                "age/of/civilizations2/jakowski/lukasz/AgentBridge", "drawHud",
                                                "(Lcom/badlogic/gdx/graphics/g2d/SpriteBatch;)V", false);
                                    }
                                }
                            };
                        }
                    };
                    cr.accept(cv, 0);
                    return cw.toByteArray();
                } catch (Throwable t) {
                    Launcher.log("FAIL|" + className + "|" + t);
                    return null;
                }
            }
            if (className.equals("age/of/civilizations2/jakowski/lukasz/Game_Action")) {
                try {
                    ClassReader cr = new ClassReader(classfileBuffer);
                    ClassWriter cw = new ClassWriter(cr, ClassWriter.COMPUTE_MAXS);
                    ClassVisitor cv = new ClassVisitor(Opcodes.ASM9, cw) {
                        @Override
                        public MethodVisitor visitMethod(int access, String name, String desc,
                                                         String signature, String[] exceptions) {
                            MethodVisitor mv = super.visitMethod(access, name, desc, signature, exceptions);
                            if (!name.equals("hideExtraViews")) {
                                return mv;
                            }
                            return new MethodVisitor(Opcodes.ASM9, mv) {
                                @Override
                                public void visitInsn(int opcode) {
                                    if (opcode == Opcodes.RETURN) {
                                        mv.visitMethodInsn(Opcodes.INVOKESTATIC,
                                                "age/of/civilizations2/jakowski/lukasz/AgentBridge",
                                                "restoreLockedViews", "()V", false);
                                    }
                                    super.visitInsn(opcode);
                                }
                            };
                        }
                    };
                    cr.accept(cv, 0);
                    return cw.toByteArray();
                } catch (Throwable t) {
                    Launcher.log("FAIL|" + className + "|" + t);
                    return null;
                }
            }
            return null;
        }
    }
}
