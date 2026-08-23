import java.io.File;
import java.io.FileInputStream;
import java.io.ObjectInputStream;
import java.io.ObjectStreamClass;
import java.io.ObjectStreamField;
import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * AoC2 serialized-object dumper.
 * Usage: java -cp "<game-aoc2.jar>;<build>" SaveDump <file> [maxDepth]
 * Renders the Java-serialized object graph as JSON. Handles cycles via $refN.
 */
public class SaveDump {
    static IdentityHashMap<Object, Integer> seen = new IdentityHashMap<Object, Integer>();
    static int idCounter = 0;
    static int maxDepth = 10;

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: SaveDump <file> [maxDepth]");
            System.exit(2);
        }
        if (args.length > 1) maxDepth = Integer.parseInt(args[1]);
        ObjectInputStream in = new ObjectInputStream(new FileInputStream(new File(args[0])));
        Object root = in.readUnshared();
        in.close();
        StringBuilder sb = new StringBuilder();
        write(root, sb, 0);
        System.out.println(sb.toString());
    }

    static void write(Object o, StringBuilder sb, int depth) {
        if (o == null) { sb.append("null"); return; }
        if (o instanceof String) { writeString((String) o, sb); return; }
        if (o instanceof Number || o instanceof Boolean || o instanceof Character) {
            if (o instanceof Character) writeString(String.valueOf(o), sb);
            else sb.append(o.toString());
            return;
        }
        if (o instanceof Class) { writeString(((Class<?>) o).getName(), sb); return; }
        if (o instanceof Enum) { writeString(((Enum<?>) o).name(), sb); return; }
        if (o instanceof java.util.Date) { sb.append(((java.util.Date) o).getTime()); return; }

        Integer id = seen.get(o);
        if (id != null) { sb.append("\"$ref").append(id).append("\""); return; }
        seen.put(o, idCounter++);

        Class<?> c = o.getClass();
        if (depth > maxDepth) { writeString("{" + c.getSimpleName() + "..}", sb); return; }

        if (o instanceof Map) {
            sb.append('{');
            boolean first = true;
            for (Object k : ((Map<?, ?>) o).keySet()) {
                if (!first) sb.append(',');
                first = false;
                writeString(String.valueOf(k), sb);
                sb.append(':');
                write(((Map<?, ?>) o).get(k), sb, depth + 1);
            }
            sb.append('}');
            return;
        }
        if (o instanceof List) {
            sb.append('[');
            List<?> l = (List<?>) o;
            for (int i = 0; i < l.size(); i++) {
                if (i > 0) sb.append(',');
                write(l.get(i), sb, depth + 1);
            }
            sb.append(']');
            return;
        }
        if (o instanceof Set) {
            sb.append('[');
            boolean first = true;
            for (Object e : (Set<?>) o) {
                if (!first) sb.append(',');
                first = false;
                write(e, sb, depth + 1);
            }
            sb.append(']');
            return;
        }
        if (c.isArray()) {
            sb.append('[');
            int n = Array.getLength(o);
            for (int i = 0; i < n; i++) {
                if (i > 0) sb.append(',');
                write(Array.get(o, i), sb, depth + 1);
            }
            sb.append(']');
            return;
        }

        ObjectStreamField[] fields = objectStreamFields(c);
        if (fields.length == 0) fields = declaredFields(c);
        sb.append('{');
        boolean first = true;
        for (ObjectStreamField f : fields) {
            if (!first) sb.append(',');
            first = false;
            writeString(f.getName(), sb);
            sb.append(':');
            write(getFieldValue(o, f), sb, depth + 1);
        }
        sb.append('}');
    }

    static ObjectStreamField[] objectStreamFields(Class<?> c) {
        try {
            ObjectStreamClass osc = ObjectStreamClass.lookup(c);
            return osc == null ? new ObjectStreamField[0] : osc.getFields();
        } catch (Throwable t) {
            return new ObjectStreamField[0];
        }
    }

    static ObjectStreamField[] declaredFields(Class<?> c) {
        List<ObjectStreamField> out = new ArrayList<ObjectStreamField>();
        for (Class<?> k = c; k != null && k != Object.class; k = k.getSuperclass()) {
            for (Field f : k.getDeclaredFields()) {
                if (f.isSynthetic() || Modifier.isStatic(f.getModifiers())) continue;
                out.add(new ObjectStreamField(f.getName(), f.getType()));
            }
        }
        return out.toArray(new ObjectStreamField[0]);
    }

    static Object getFieldValue(Object o, ObjectStreamField f) {
        try {
            Field rf = findField(o.getClass(), f.getName());
            rf.setAccessible(true);
            return rf.get(o);
        } catch (Throwable t) {
            return null;
        }
    }

    static Field findField(Class<?> c, String name) {
        for (Class<?> k = c; k != null; k = k.getSuperclass()) {
            try {
                return k.getDeclaredField(name);
            } catch (NoSuchFieldException e) { }
        }
        return null;
    }

    static void writeString(String s, StringBuilder sb) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char ch = s.charAt(i);
            switch (ch) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (ch < 0x20) sb.append(String.format("\\u%04x", (int) ch));
                    else sb.append(ch);
            }
        }
        sb.append('"');
    }
}
