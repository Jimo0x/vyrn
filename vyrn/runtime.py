"""Runtime C embarqué dans chaque programme Vyrn compilé."""

PRELUDE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdarg.h>
#include <math.h>
#include <ctype.h>
#include <time.h>

typedef const char* vy_str;

static void vy_panic(const char* msg, int line) {
    fflush(stdout);
    fprintf(stderr, "erreur d'execution (ligne %d) : %s\n", line, msg);
    exit(1);
}

static void* vy_alloc(size_t n) {
    void* p = malloc(n ? n : 1);
    if (!p) { fprintf(stderr, "memoire epuisee\n"); exit(1); }
    return p;
}

static void* vy_realloc(void* p, size_t n) {
    p = realloc(p, n ? n : 1);
    if (!p) { fprintf(stderr, "memoire epuisee\n"); exit(1); }
    return p;
}

static vy_str vy_strndup(const char* s, size_t n) {
    char* r = (char*)vy_alloc(n + 1);
    memcpy(r, s, n);
    r[n] = 0;
    return r;
}

static vy_str vy_strdup(const char* s) { return vy_strndup(s, strlen(s)); }

/* ---- tampon de chaîne ---- */
typedef struct { char* d; size_t n, cap; } vy_buf;

static void vy_buf_add(vy_buf* b, const char* s) {
    size_t k = strlen(s);
    if (b->n + k + 1 > b->cap) {
        b->cap = (b->n + k + 1) * 2;
        b->d = (char*)vy_realloc(b->d, b->cap);
    }
    memcpy(b->d + b->n, s, k);
    b->n += k;
    b->d[b->n] = 0;
}

static vy_str vy_buf_done(vy_buf* b) { return b->d ? b->d : ""; }

/* ---- conversions ---- */
static vy_str vy_str_of_int(int64_t v) {
    char buf[32];
    snprintf(buf, sizeof buf, "%lld", (long long)v);
    return vy_strdup(buf);
}

static vy_str vy_str_of_float(double v) {
    char buf[64];
    if (isnan(v)) return "nan";
    if (isinf(v)) return v > 0 ? "inf" : "-inf";
    snprintf(buf, sizeof buf, "%.15g", v);
    if (!strpbrk(buf, ".e")) strcat(buf, ".0");
    return vy_strdup(buf);
}

static vy_str vy_str_of_bool(bool b) { return b ? "true" : "false"; }

static vy_str vy_str_of_str(vy_str s) { return s; }

static vy_str vy_repr_str(vy_str s) {
    vy_buf b = {0};
    vy_buf_add(&b, "\"");
    vy_buf_add(&b, s);
    vy_buf_add(&b, "\"");
    return vy_buf_done(&b);
}

static int64_t vy_str_to_int(vy_str s, int line) {
    char* end;
    while (isspace((unsigned char)*s)) s++;
    long long v = strtoll(s, &end, 10);
    while (isspace((unsigned char)*end)) end++;
    if (end == s || *end) vy_panic("conversion en int impossible", line);
    return (int64_t)v;
}

static double vy_str_to_float(vy_str s, int line) {
    char* end;
    while (isspace((unsigned char)*s)) s++;
    double v = strtod(s, &end);
    while (isspace((unsigned char)*end)) end++;
    if (end == s || *end) vy_panic("conversion en float impossible", line);
    return v;
}

/* ---- chaînes ---- */
static vy_str vy_str_concat(vy_str a, vy_str b) {
    size_t la = strlen(a), lb = strlen(b);
    char* r = (char*)vy_alloc(la + lb + 1);
    memcpy(r, a, la);
    memcpy(r + la, b, lb + 1);
    return r;
}

static bool vy_str_eq(vy_str a, vy_str b) { return strcmp(a, b) == 0; }

static vy_str vy_str_index(vy_str s, int64_t i, int line) {
    int64_t n = (int64_t)strlen(s);
    if (i < 0) i += n;
    if (i < 0 || i >= n) vy_panic("indice de chaine hors limites", line);
    return vy_strndup(s + i, 1);
}

static vy_str vy_s_repeat(vy_str s, int64_t k) {
    vy_buf b = {0};
    for (int64_t i = 0; i < k; i++) vy_buf_add(&b, s);
    return vy_buf_done(&b);
}

static vy_str vy_s_upper(vy_str s) {
    char* r = (char*)vy_strdup(s);
    for (char* p = r; *p; p++) *p = (char)toupper((unsigned char)*p);
    return r;
}

static vy_str vy_s_lower(vy_str s) {
    char* r = (char*)vy_strdup(s);
    for (char* p = r; *p; p++) *p = (char)tolower((unsigned char)*p);
    return r;
}

static vy_str vy_s_trim(vy_str s) {
    while (isspace((unsigned char)*s)) s++;
    size_t n = strlen(s);
    while (n && isspace((unsigned char)s[n - 1])) n--;
    return vy_strndup(s, n);
}

static bool vy_s_contains(vy_str s, vy_str t) { return strstr(s, t) != NULL; }

static bool vy_s_starts_with(vy_str s, vy_str t) { return strncmp(s, t, strlen(t)) == 0; }

static bool vy_s_ends_with(vy_str s, vy_str t) {
    size_t a = strlen(s), b = strlen(t);
    return b <= a && strcmp(s + a - b, t) == 0;
}

static int64_t vy_s_find(vy_str s, vy_str t) {
    const char* p = strstr(s, t);
    return p ? (int64_t)(p - s) : -1;
}

static vy_str vy_s_slice(vy_str s, int64_t a, int64_t b) {
    int64_t n = (int64_t)strlen(s);
    if (a < 0) a += n;
    if (b < 0) b += n;
    if (a < 0) a = 0;
    if (b > n) b = n;
    if (a >= b) return "";
    return vy_strndup(s + a, (size_t)(b - a));
}

static vy_str vy_s_replace(vy_str s, vy_str from, vy_str to, int line) {
    size_t k = strlen(from);
    if (k == 0) vy_panic("replace : motif vide", line);
    vy_buf b = {0};
    const char* p;
    while ((p = strstr(s, from))) {
        vy_str chunk = vy_strndup(s, (size_t)(p - s));
        vy_buf_add(&b, chunk);
        vy_buf_add(&b, to);
        s = p + k;
    }
    vy_buf_add(&b, s);
    return vy_buf_done(&b);
}

/* ---- E/S ---- */
static void vy_print(int n, ...) {
    va_list ap;
    va_start(ap, n);
    for (int i = 0; i < n; i++) {
        if (i) fputc(' ', stdout);
        fputs(va_arg(ap, vy_str), stdout);
    }
    va_end(ap);
    fputc('\n', stdout);
}

static vy_str vy_input(vy_str prompt) {
    fputs(prompt, stdout);
    fflush(stdout);
    vy_buf b = {0};
    char chunk[256];
    while (fgets(chunk, sizeof chunk, stdin)) {
        vy_buf_add(&b, chunk);
        if (b.n && b.d[b.n - 1] == '\n') break;
    }
    if (b.n && b.d[b.n - 1] == '\n') b.d[--b.n] = 0;
    if (b.n && b.d[b.n - 1] == '\r') b.d[--b.n] = 0;
    return vy_buf_done(&b);
}

/* ---- maths ---- */
static int64_t vy_idiv(int64_t a, int64_t b, int line) {
    if (b == 0) vy_panic("division par zero", line);
    return a / b;
}

static int64_t vy_imod(int64_t a, int64_t b, int line) {
    if (b == 0) vy_panic("modulo par zero", line);
    return a % b;
}

static int64_t vy_iabs(int64_t a) { return a < 0 ? -a : a; }
static int64_t vy_imin(int64_t a, int64_t b) { return a < b ? a : b; }
static int64_t vy_imax(int64_t a, int64_t b) { return a > b ? a : b; }

static int64_t vy_rand_int(int64_t lo, int64_t hi, int line) {
    if (hi < lo) vy_panic("rand_int : max < min", line);
    uint64_t r = ((uint64_t)rand() << 31) ^ (uint64_t)rand();
    return lo + (int64_t)(r % (uint64_t)(hi - lo + 1));
}

static double vy_clock(void) { return (double)clock() / CLOCKS_PER_SEC; }

static void vy_assert(bool c, vy_str msg, int line) {
    if (!c) vy_panic(vy_str_concat("assertion echouee : ", msg), line);
}
'''
