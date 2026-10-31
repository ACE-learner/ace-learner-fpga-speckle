#include"debug.h"
#include"basic_block.h"
#include<iostream>
#include<cstdio>
#include<cmath>
#include "xtime_l.h"
using namespace std;

/* ============================================================================
 * ARM 端关键点后处理（与 PC 端 decode_box 解码一致）
 *   out0/out1 : int16 特征图，值 = round(float * 512)
 *   布局      : CHW，[anchor*(5+36) + 属性][grid][grid]
 *   输出      : 归一化坐标 (0~1)，与图片尺寸无关
 *               1) 串口打印  K <帧> <类> <nx> <ny> <nw> <nh> <score>
 *               2) SD 小文件 yolo_test\kp_<帧>.bin
 *                  每点 24 B = nx,ny,nw,nh,score (float32) + cls (int32)
 * ========================================================================== */
#define KP_NC        36
#define KP_SCALE     512.0f
#define KP_PRINT     1          /* 串口打印（调试用，正式演示可改 0 提速） */
#define KP_WRITEFILE 0          /* 写 SD 小文件（按需求关闭） */
#define KP_CONF      0.001f     /* 输出阈值（打印/写文件用） */

static const float KP_ANCH[6][2] = {
    {10.f, 14.f}, {23.f, 27.f}, {37.f, 58.f},
    {81.f, 82.f}, {135.f, 169.f}, {344.f, 319.f}
};
static const int KP_MASK0[3] = {3, 4, 5};   /* 13x13 */
static const int KP_MASK1[3] = {1, 2, 3};   /* 26x26 */

struct KPoint {
    int   cls;
    float nx, ny, nw, nh, score;   /* 全部归一化到 0~1 */
};

static inline float kp_sigmoid(float v)
{
    if (v >= 0.0f) { float e = expf(-v); return 1.0f / (1.0f + e); }
    float e = expf(v);
    return e / (1.0f + e);
}

static void kp_scan(const data_t* feat, int g,
                    float best_score[KP_NC], int best_pos[KP_NC],
                    int best_grid[KP_NC], int best_anchor[KP_NC])
{
    const int plane = g * g;
    for (int a = 0; a < 3; a++) {
        const int base = a * (5 + KP_NC);
        for (int pos = 0; pos < plane; pos++) {
            float obj = kp_sigmoid((float)feat[(base + 4) * plane + pos] / KP_SCALE);
            if (obj < 0.01f) continue;
            /* YOLO 标准：每个框先取 36 类 argmax 作为自己的类别（与原工程 yolo2.py 一致） */
            int   cbest = 0;
            float clmax = kp_sigmoid((float)feat[(base + 5) * plane + pos] / KP_SCALE);
            for (int c = 1; c < KP_NC; c++) {
                float cl = kp_sigmoid((float)feat[(base + 5 + c) * plane + pos] / KP_SCALE);
                if (cl > clmax) { clmax = cl; cbest = c; }
            }
            float s = obj * clmax;
            if (s > best_score[cbest]) {
                best_score[cbest] = s;
                best_pos[cbest] = pos;
                best_grid[cbest] = g;
                best_anchor[cbest] = a;
            }
        }
    }
}

static int kp_extract(const data_t* out0, const data_t* out1, KPoint kp[KP_NC])
{
    float bs[KP_NC];
    int bp[KP_NC], bg[KP_NC], ba[KP_NC];

    for (int c = 0; c < KP_NC; c++) {
        bs[c] = -1.0f; bp[c] = -1; bg[c] = 0; ba[c] = 0;
    }
    kp_scan(out0, 13, bs, bp, bg, ba);
    kp_scan(out1, 26, bs, bp, bg, ba);

    int n = 0;
    for (int c = 0; c < KP_NC; c++) {
        if (bp[c] < 0 || bs[c] < KP_CONF) continue;

        const int g     = bg[c];
        const int plane = g * g;
        const int pos   = bp[c];
        const int gy    = pos / g;
        const int gx    = pos % g;
        const int a     = ba[c];
        const int ai    = (g == 13) ? KP_MASK0[a] : KP_MASK1[a];
        const data_t* feat = (g == 13) ? out0 : out1;
        const int base  = a * (5 + KP_NC);

        float tx = (float)feat[(base + 0) * plane + pos] / KP_SCALE;
        float ty = (float)feat[(base + 1) * plane + pos] / KP_SCALE;
        float tw = (float)feat[(base + 2) * plane + pos] / KP_SCALE;
        float th = (float)feat[(base + 3) * plane + pos] / KP_SCALE;

        kp[n].cls   = c;
        kp[n].nx    = (kp_sigmoid(tx) + (float)gx) / (float)g;
        kp[n].ny    = (kp_sigmoid(ty) + (float)gy) / (float)g;
        kp[n].nw    = expf(tw) * KP_ANCH[ai][0] / 416.0f;
        kp[n].nh    = expf(th) * KP_ANCH[ai][1] / 416.0f;
        kp[n].score = bs[c];
        n++;
    }
    return n;
}

/* 写 SD 小文件：每点 24 字节 */
static void kp_write_file(const string& path, const KPoint kp[KP_NC], int n)
{
    FILE* fp = fopen(path.c_str(), "wb");
    if (fp == NULL) return;
    for (int i = 0; i < n; i++) {
        float rec[5];
        int   cls = kp[i].cls;
        rec[0] = kp[i].nx;
        rec[1] = kp[i].ny;
        rec[2] = kp[i].nw;
        rec[3] = kp[i].nh;
        rec[4] = kp[i].score;
        fwrite(rec, sizeof(float), 5, fp);
        fwrite(&cls, sizeof(int), 1, fp);
    }
    fclose(fp);
}

void yolo_test(string weight_dir, string ref_dir, int img_num)
{
    data_t* in = new data_t[3*416*416];
    data_t* out0 = new data_t[OUT_CH*13*13];
    data_t* out1 = new data_t[OUT_CH*26*26];

    XTime tEnd, tCur;
    u32 tUsed;

    conv_init();

    Yolo4_Tiny* yolo4_tiny = new Yolo4_Tiny();
    yolo4_tiny->load_weight(weight_dir);

    for(int i = 0; i < img_num; i++)
    {
        cout << "processing image " << i << endl;

        string img_path  = ref_dir + "\\img"  + to_string(i) + ".bin";

        /* 检查输入文件是否存在（必须用 FatFS 接口，C stdio 的 fopen 在本工程不可用） */
        {
            FIL chk;
            FRESULT frc = f_open(&chk, img_path.c_str(), FA_READ);
            if (frc != FR_OK) {
                printf("ERROR: cannot open %s (rc=%d)\n", img_path.c_str(), frc);
                printf("STOP at frame %d\n", i);
                fflush(stdout);
                break;
            }
            f_close(&chk);
        }

        read_params(img_path, in, 3*416*416);

        Xil_DCacheFlush();

        XTime_GetTime(&tCur);

        yolo4_tiny->forward(in, out0, out1);

        Xil_DCacheInvalidateRange(
            (u32)((unsigned int)out0 & 0xffffffe0),
            32*((OUT_CH*13*13*sizeof(data_t))/32+2)
        );

        Xil_DCacheInvalidateRange(
            (u32)((unsigned int)out1 & 0xffffffe0),
            32*((OUT_CH*26*26*sizeof(data_t))/32+2)
        );

        XTime_GetTime(&tEnd);
        tUsed = ((tEnd - tCur) * 1000000) / COUNTS_PER_SECOND;

        cout << "image " << i << " time elapsed is " << tUsed << " us" << endl;

        /* ===== ARM 端关键点后处理（归一化坐标） ===== */
        XTime t0, t1;
        XTime_GetTime(&t0);
        KPoint kp[KP_NC];
        int nkp = kp_extract(out0, out1, kp);
        XTime_GetTime(&t1);
        u32 kpUs = (u32)(((t1 - t0) * 1000000) / COUNTS_PER_SECOND);

#if KP_PRINT
        printf("KPT %d %lu\n", i, (unsigned long)kpUs);
        printf("KP %d %d/%d\n", i, nkp, KP_NC);
        for (int k = 0; k < nkp; k++) {
            printf("K %d %d %.5f %.5f %.5f %.5f %.3f\n",
                   i, kp[k].cls, kp[k].nx, kp[k].ny, kp[k].nw, kp[k].nh, kp[k].score);
        }
        fflush(stdout);
#endif

#if KP_WRITEFILE
        {
            string kp_path = ref_dir + "\\kp_" + to_string(i) + ".bin";
            kp_write_file(kp_path, kp, nkp);
        }
#endif

        /* 默认不再写 415 KB 的 out 文件（如需对比可把下面两行放开） */
        // write_data(ref_dir + "\\out0_" + to_string(i) + ".bin", out0, OUT_CH*13*13);
        // write_data(ref_dir + "\\out1_" + to_string(i) + ".bin", out1, OUT_CH*26*26);
    }

    printf("ALL DONE %d frames\n", img_num);
    fflush(stdout);

    delete [] in;
    delete [] out0;
    delete [] out1;
    delete yolo4_tiny;
}
