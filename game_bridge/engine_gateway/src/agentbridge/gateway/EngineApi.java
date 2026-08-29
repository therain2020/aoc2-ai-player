package agentbridge.gateway;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * EngineApi — cached reflection access layer for the protected engine API.
 *
 * The engine (Age of Civilizations II) exposes its gameplay API as
 * package-protected members of age.of.civilizations2.jakowski.lukasz.* . The
 * legacy AgentBridge lived inside the engine package and therefore called
 * them directly; the source-level bridge (EngineGateway) lives in
 * agentbridge.gateway per FR-002 (no engine class changes allowed), so
 * protected members are reached through reflection. Java-8 only, no ASM.
 */
final class EngineApi {

    private EngineApi() {
    }

    /** RuntimeException wrapper so callers may catch Throwable uniformly. */
    static final class EngineException extends RuntimeException {
        EngineException(String msg, Throwable cause) {
            super(msg, cause);
        }
    }

    private static final Map<String, Class<?>> CLASSES = new ConcurrentHashMap<String, Class<?>>();
    private static final Map<String, Method> METHODS = new ConcurrentHashMap<String, Method>();
    private static final Map<String, Constructor<?>> CTORS = new ConcurrentHashMap<String, Constructor<?>>();

    /** Engine class handle (e.g. "age.of.civilizations2.jakowski.lukasz.CFG"). */
    static Class<?> cls(String name) {
        Class<?> c = CLASSES.get(name);
        if (c == null) {
            try {
                c = Class.forName(name);
            } catch (ClassNotFoundException e) {
                throw new EngineException("engine class not found: " + name, e);
            }
            CLASSES.put(name, c);
        }
        return c;
    }

    /**
     * Invoke a method. {@code target} may be an engine object (instance call)
     * or a Class (static call).
     */
    static Object call(Object target, String name, Object... args) {
        boolean stat = target instanceof Class;
        Class<?> owner = stat ? (Class<?>) target : target.getClass();
        try {
            Method m = findMethod(owner, name, args);
            return m.invoke(stat ? null : target, args);
        } catch (Throwable t) {
            throw new EngineException("call " + owner.getName() + "." + name + " failed: " + t, t);
        }
    }

    /** Read a field. target may be an engine object or a Class (static field). */
    static Object get(Object target, String fieldName) {
        boolean stat = target instanceof Class;
        Class<?> owner = stat ? (Class<?>) target : target.getClass();
        try {
            Field f = findField(owner, fieldName);
            return f.get(stat ? null : target);
        } catch (Throwable t) {
            throw new EngineException("get " + owner.getName() + "." + fieldName + " failed: " + t, t);
        }
    }

    /** Write a field. target may be an engine object or a Class (static field). */
    static void set(Object target, String fieldName, Object value) {
        boolean stat = target instanceof Class;
        Class<?> owner = stat ? (Class<?>) target : target.getClass();
        try {
            Field f = findField(owner, fieldName);
            f.set(stat ? null : target, value);
        } catch (Throwable t) {
            throw new EngineException("set " + owner.getName() + "." + fieldName + " failed: " + t, t);
        }
    }

    /** Constructor call, e.g. new Start_The_Game_Data(false). */
    static Object newInst(Class<?> c, Object... args) {
        try {
            String key = c.getName() + "#" + mkTypesKey(args);
            Constructor<?> ct = CTORS.get(key);
            if (ct == null) {
                for (Constructor<?> k : c.getDeclaredConstructors()) {
                    if (k.getParameterTypes().length == args.length && matchTypes(k.getParameterTypes(), args)) {
                        ct = k;
                        break;
                    }
                }
                if (ct == null) {
                    throw new NoSuchMethodException(c.getName() + "<init>");
                }
                ct.setAccessible(true);
                CTORS.put(key, ct);
            }
            return ct.newInstance(args);
        } catch (Throwable t) {
            throw new EngineException("new " + c.getName() + " failed: " + t, t);
        }
    }

    /** Enum constant by name (e.g. Menu.eSTART_THE_GAME). */
    static Object enumConst(String clsName, String constantName) {
        Object[] consts = cls(clsName).getEnumConstants();
        if (consts != null) {
            for (Object v : consts) {
                if (v.toString().equals(constantName)) {
                    return v;
                }
            }
        }
        throw new EngineException("enum constant not found: " + clsName + "." + constantName, null);
    }

    // ---- internals ----

    private static Method findMethod(Class<?> clazz, String name, Object[] args) throws NoSuchMethodException {
        String key = clazz.getName() + "#" + name + "(" + mkTypesKey(args) + ")";
        Method cached = METHODS.get(key);
        if (cached != null) {
            return cached;
        }
        Method best = null;
        int bestCost = Integer.MAX_VALUE;
        for (Class<?> c = clazz; c != null; c = c.getSuperclass()) {
            for (Method m : c.getDeclaredMethods()) {
                if (!m.getName().equals(name)) {
                    continue;
                }
                Class<?>[] pt = m.getParameterTypes();
                if (pt.length != args.length) {
                    continue;
                }
                int cost = matchCost(pt, args);
                if (cost < 0 || cost >= bestCost) {
                    continue;
                }
                best = m;
                bestCost = cost;
            }
            if (best != null) {
                break; // subclass definitions take precedence
            }
        }
        if (best == null) {
            throw new NoSuchMethodException(clazz.getName() + "." + name);
        }
        best.setAccessible(true);
        METHODS.put(key, best);
        return best;
    }

    private static Field findField(Class<?> clazz, String name) {
        for (Class<?> c = clazz; c != null; c = c.getSuperclass()) {
            try {
                Field f = c.getDeclaredField(name);
                f.setAccessible(true);
                return f;
            } catch (NoSuchFieldException ignored) {
            }
        }
        throw new EngineException("field not found: " + clazz.getName() + "." + name, null);
    }

    private static Class<?> box(Class<?> p) {
        if (!p.isPrimitive()) {
            return p;
        }
        if (p == boolean.class) {
            return Boolean.class;
        }
        if (p == byte.class) {
            return Byte.class;
        }
        if (p == short.class) {
            return Short.class;
        }
        if (p == int.class) {
            return Integer.class;
        }
        if (p == long.class) {
            return Long.class;
        }
        if (p == float.class) {
            return Float.class;
        }
        if (p == double.class) {
            return Double.class;
        }
        if (p == char.class) {
            return Character.class;
        }
        return p;
    }

    /** -1 = not compatible; otherwise lower is better (0 = exact). */
    private static int matchCost(Class<?>[] pt, Object[] args) {
        int sum = 0;
        for (int i = 0; i < pt.length; ++i) {
            Object a = args[i];
            if (a == null) {
                if (pt[i].isPrimitive()) {
                    return -1;
                }
                sum += 1; // nullable reference — accept but non-preferred
                continue;
            }
            Class<?> at = a.getClass();
            if (at == box(pt[i])) {
                sum += 0;
            } else if (box(pt[i]).isAssignableFrom(at)) {
                sum += 1;
            } else if (!pt[i].isPrimitive() && at.isAssignableFrom(pt[i])) {
                sum += 2;
            } else {
                return -1;
            }
        }
        return sum;
    }

    private static boolean matchTypes(Class<?>[] pt, Object[] args) {
        // newInst path: arg class must be assignable to param (boxed primitives ok)
        for (int i = 0; i < pt.length; ++i) {
            Object a = args[i];
            if (a == null) {
                if (pt[i].isPrimitive()) {
                    return false;
                }
                continue;
            }
            if (!box(pt[i]).isAssignableFrom(a.getClass())) {
                return false;
            }
        }
        return true;
    }

    private static String mkTypesKey(Object[] args) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < args.length; ++i) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(args[i] == null ? "null" : args[i].getClass().getName());
        }
        return sb.toString();
    }
}
