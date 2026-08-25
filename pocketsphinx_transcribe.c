#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct cmd_ln_s cmd_ln_t;
typedef struct arg_s arg_t;
typedef struct ps_decoder_s ps_decoder_t;

extern const arg_t *ps_args(void);
extern cmd_ln_t *cmd_ln_init(cmd_ln_t *, const arg_t *, int32_t, ...);
extern void cmd_ln_free_r(cmd_ln_t *);
extern ps_decoder_t *ps_init(cmd_ln_t *);
extern int ps_start_utt(ps_decoder_t *, const char *);
extern int ps_process_raw(ps_decoder_t *, const int16_t *, size_t, int, int);
extern int ps_end_utt(ps_decoder_t *);
extern const char *ps_get_hyp(ps_decoder_t *, int32_t *, const char **);
extern int ps_free(ps_decoder_t *);

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s audio.raw\n", argv[0]);
        return 2;
    }
    cmd_ln_t *config = cmd_ln_init(
        NULL, ps_args(), 1,
        "-hmm", "/usr/share/pocketsphinx/model/en-us/en-us",
        "-lm", "/usr/share/pocketsphinx/model/en-us/en-us.lm.bin",
        "-dict", "/usr/share/pocketsphinx/model/en-us/cmudict-en-us.dict",
        "-samprate", "16000",
        "-logfn", "/dev/null",
        NULL
    );
    if (!config) return 3;
    ps_decoder_t *ps = ps_init(config);
    if (!ps) return 4;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 5;
    if (ps_start_utt(ps, NULL) < 0) return 6;
    int16_t buf[2048];
    size_t n;
    while ((n = fread(buf, sizeof(*buf), 2048, f)) > 0)
        ps_process_raw(ps, buf, n, 0, 0);
    fclose(f);
    ps_end_utt(ps);
    int32_t score = 0;
    const char *uttid = NULL;
    const char *hyp = ps_get_hyp(ps, &score, &uttid);
    printf("%s\n", hyp ? hyp : "");
    ps_free(ps);
    cmd_ln_free_r(config);
    return 0;
}
