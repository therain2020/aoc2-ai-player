package agentbridge.gateway;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Json — minimal JSON support for the source-level bridge.
 *
 * javax.json is not available in the game JRE and we avoid third-party
 * libraries (zero-dep rule), so this file provides just enough: a tiny
 * recursive-descent parser for the /action and /plan request bodies plus
 * string escaping for building responses. Java-8 only.
 */
final class Json {

    private Json() {
    }

    /** Malformed JSON body. */
    static final class JsonException extends RuntimeException {
        JsonException(String msg) {
            super(msg);
        }
    }

    /** Parse a JSON document: Map / List / String / Number(Long|Double) / Boolean / null. */
    static Object parse(String text) {
        Parser p = new Parser(text);
        p.skipWs();
        Object v = p.parseValue();
        p.skipWs();
        if (!p.atEnd()) {
            throw new JsonException("trailing characters at offset " + p.pos);
        }
        return v;
    }

    /** Quote and escape a string for JSON output. */
    static String quote(String s) {
        if (s == null) {
            return "\"\"";
        }
        StringBuilder sb = new StringBuilder(s.length() + 2);
        sb.append('"');
        for (int i = 0; i < s.length(); ++i) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.append('"').toString();
    }

    // ---- parser ----

    private static final class Parser {
        final String s;
        int pos = 0;

        Parser(String s) {
            this.s = s == null ? "" : s;
        }

        boolean atEnd() {
            return pos >= s.length();
        }

        void skipWs() {
            while (pos < s.length()) {
                char c = s.charAt(pos);
                if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
                    ++pos;
                } else {
                    break;
                }
            }
        }

        Object parseValue() {
            skipWs();
            if (atEnd()) {
                throw new JsonException("unexpected end of input");
            }
            char c = s.charAt(pos);
            if (c == '{') {
                return parseObject();
            }
            if (c == '[') {
                return parseArray();
            }
            if (c == '"') {
                return parseString();
            }
            if (c == 't') {
                expect("true");
                return Boolean.TRUE;
            }
            if (c == 'f') {
                expect("false");
                return Boolean.FALSE;
            }
            if (c == 'n') {
                expect("null");
                return null;
            }
            if (c == '-' || (c >= '0' && c <= '9')) {
                return parseNumber();
            }
            throw new JsonException("unexpected character '" + c + "' at offset " + pos);
        }

        void expect(String token) {
            if (!s.startsWith(token, pos)) {
                throw new JsonException("expected " + token + " at offset " + pos);
            }
            pos += token.length();
        }

        Map<String, Object> parseObject() {
            Map<String, Object> m = new LinkedHashMap<String, Object>();
            ++pos; // {
            skipWs();
            if (!atEnd() && s.charAt(pos) == '}') {
                ++pos;
                return m;
            }
            for (;;) {
                skipWs();
                if (atEnd() || s.charAt(pos) != '"') {
                    throw new JsonException("expected string key at offset " + pos);
                }
                String key = parseString();
                skipWs();
                if (atEnd() || s.charAt(pos) != ':') {
                    throw new JsonException("expected ':' at offset " + pos);
                }
                ++pos;
                Object v = parseValue();
                m.put(key, v);
                skipWs();
                if (atEnd()) {
                    throw new JsonException("unterminated object");
                }
                char c = s.charAt(pos);
                if (c == ',') {
                    ++pos;
                } else if (c == '}') {
                    ++pos;
                    return m;
                } else {
                    throw new JsonException("expected ',' or '}' at offset " + pos);
                }
            }
        }

        List<Object> parseArray() {
            List<Object> list = new ArrayList<Object>();
            ++pos; // [
            skipWs();
            if (!atEnd() && s.charAt(pos) == ']') {
                ++pos;
                return list;
            }
            for (;;) {
                list.add(parseValue());
                skipWs();
                if (atEnd()) {
                    throw new JsonException("unterminated array");
                }
                char c = s.charAt(pos);
                if (c == ',') {
                    ++pos;
                } else if (c == ']') {
                    ++pos;
                    return list;
                } else {
                    throw new JsonException("expected ',' or ']' at offset " + pos);
                }
            }
        }

        String parseString() {
            ++pos; // "
            StringBuilder sb = new StringBuilder();
            for (;;) {
                if (atEnd()) {
                    throw new JsonException("unterminated string");
                }
                char c = s.charAt(pos++);
                if (c == '"') {
                    return sb.toString();
                }
                if (c == '\\') {
                    if (atEnd()) {
                        throw new JsonException("unterminated escape");
                    }
                    char e = s.charAt(pos++);
                    switch (e) {
                        case '"': sb.append('"'); break;
                        case '\\': sb.append('\\'); break;
                        case '/': sb.append('/'); break;
                        case 'b': sb.append('\b'); break;
                        case 'f': sb.append('\f'); break;
                        case 'n': sb.append('\n'); break;
                        case 'r': sb.append('\r'); break;
                        case 't': sb.append('\t'); break;
                        case 'u':
                            if (pos + 4 > s.length()) {
                                throw new JsonException("bad unicode escape");
                            }
                            int cp = 0;
                            for (int k = 0; k < 4; ++k) {
                                char h = s.charAt(pos + k);
                                int d = Character.digit(h, 16);
                                if (d < 0) {
                                    throw new JsonException("bad unicode escape");
                                }
                                cp = (cp << 4) | d;
                            }
                            pos += 4;
                            sb.append((char) cp);
                            break;
                        default:
                            throw new JsonException("bad escape '\\" + e + "'");
                    }
                } else if (c < 0x20) {
                    throw new JsonException("raw control character in string");
                } else {
                    sb.append(c);
                }
            }
        }

        Number parseNumber() {
            int start = pos;
            if (!atEnd() && s.charAt(pos) == '-') {
                ++pos;
            }
            boolean isDouble = false;
            while (!atEnd()) {
                char c = s.charAt(pos);
                if (c >= '0' && c <= '9') {
                    ++pos;
                } else if (c == '.' || c == 'e' || c == 'E' || c == '+' || c == '-') {
                    isDouble = true;
                    ++pos;
                } else {
                    break;
                }
            }
            String tok = s.substring(start, pos);
            try {
                if (isDouble) {
                    return Double.valueOf(tok);
                }
                return Long.valueOf(tok);
            } catch (NumberFormatException e) {
                throw new JsonException("bad number '" + tok + "'");
            }
        }
    }

    // ---- helpers for callers ----

    /** String value from a params map. */
    static String asStr(Object v) {
        return v == null ? null : v.toString();
    }

    /** Parse map entry as int (tolerates Long/Double). */
    static int asInt(Object v) {
        if (v == null) {
            throw new JsonException("missing numeric value");
        }
        if (v instanceof Number) {
            return ((Number) v).intValue();
        }
        try {
            return Integer.parseInt(v.toString().trim());
        } catch (NumberFormatException e) {
            throw new JsonException("expected number, got '" + v + "'");
        }
    }

    /** First key present in the map (keys tried in order). */
    static Object first(Map<String, Object> m, String... keys) {
        for (String k : keys) {
            if (m.containsKey(k)) {
                return m.get(k);
            }
        }
        return null;
    }
}
