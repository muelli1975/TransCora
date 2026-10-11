/* TransCora's strict, portable bridge to the BSD edge264-mvc/mvc-source core. */
#include "mvcsource.c"
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif

static int decode(int argc, char **argv) {
    if (argc != 8) { fprintf(stderr, "base dependent fps_num fps_den start count probe\n"); return 2; }
    int64_t num = strtoll(argv[3], NULL, 10), den = strtoll(argv[4], NULL, 10);
    int start = atoi(argv[5]), limit = atoi(argv[6]), probe = atoi(argv[7]);
    if (num <= 0 || den <= 0 || start < 0 || limit < 0) return 2;
    char err[1024] = {0};
    MvcSource *s = mvc_open2(argv[1], strcmp(argv[2], "-") ? argv[2] : NULL,
        -1, MVC_SBS, 0, num, den, 32, NULL, NULL, err, sizeof(err));
    if (!s) { fprintf(stderr, "MVC: %s\n", err); return 3; }
    const MvcInfo *v = mvc_info(s);
    if (!v->is_mvc || v->layout != MVC_SBS || !s->cur.samples_mvc[0]) {
        /* frame 0 is cached at open; get_frame establishes cur before checking. */
        if (ensure_source_frame(s, 0, err, sizeof(err)) < 0 || !v->is_mvc || !s->cur.samples_mvc[0]) {
            fprintf(stderr, "MVC: complete stereo pair missing\n"); mvc_close(s); return 4;
        }
    }
    if (probe) {
        if (s->cur.flags) { fprintf(stderr, "MVC: damaged initial stereo pair\n"); mvc_close(s); return 7; }
        printf("{\"width\":%d,\"height\":%d,\"frames\":%d,\"mvc\":true}\n", v->width, v->height, v->num_frames);
        mvc_close(s); return 0;
    }
    if (start >= v->num_frames) { mvc_close(s); return 5; }
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    size_t y = (size_t)v->width*v->height, c = y/4;
    uint8_t *buf = malloc(y+2*c);
    if (!buf) { mvc_close(s); return 6; }
    printf("YUV4MPEG2 W%d H%d F%lld:%lld Ip A1:1 C420jpeg\n", v->width, v->height,
        (long long)num, (long long)den);
    int end = limit && limit < v->num_frames-start ? start+limit : v->num_frames;
    for (int n = start; n < end; ++n) {
        if (ensure_source_frame(s, n, err, sizeof(err)) < 0 || !s->cur.samples_mvc[0] || s->cur.flags) {
            fprintf(stderr, "MVC frame %d: missing/damaged stereo pair: %s\n", n, err);
            free(buf); mvc_close(s); return 7;
        }
        if (mvc_get_frame(s, n, buf, v->width, buf+y, v->width/2, buf+y+c, v->width/2,
                err, sizeof(err)) < 0 || fputs("FRAME\n", stdout) == EOF || fwrite(buf, 1, y+2*c, stdout) != y+2*c) {
            fprintf(stderr, "MVC frame %d: %s\n", n, err); free(buf); mvc_close(s); return 8;
        }
    }
    free(buf); mvc_close(s);
    return fflush(stdout) ? 9 : 0;
}
#ifdef _WIN32
int wmain(int argc, wchar_t **wargv) {
    char **argv = calloc((size_t)argc, sizeof(char*));
    if (!argv) return 6;
    for (int i=0; i<argc; i++) {
        int n = WideCharToMultiByte(CP_UTF8, 0, wargv[i], -1, NULL, 0, NULL, NULL);
        argv[i] = malloc(n);
        if (!argv[i]) return 6;
        WideCharToMultiByte(CP_UTF8, 0, wargv[i], -1, argv[i], n, NULL, NULL);
    }
    int r = decode(argc, argv);
    for (int i=0; i<argc; i++) free(argv[i]);
    free(argv); return r;
}
#else
int main(int argc, char **argv) { return decode(argc, argv); }
#endif
