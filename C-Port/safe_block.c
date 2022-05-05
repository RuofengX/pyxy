#include <time.h>
#include <cJSON.h>

#define PYXY_KEY_LENGTH 16

struct payload_t {
    int length;
    unsigned char data[];
};

struct ukpt_t {
    char uuid[32];
    char key[PYXY_KEY_LENGTH];
    time_t timestamp;
    cJSON *payload;    
};

struct ukpt_t *byte_to_ukpt(const struct ukpt_t *ukpt, int length);
    cJSON *ukpt_json = NULL;
    // TODO: 将网络收到的字节串存储进ukpt


void build_ukpt_from_bytes(unsigned char *content, int len, unsigned char *out)
{
    int i;
    for (i = 0; i < len; i++)
    {
        out[i] = content[i];
    }
}