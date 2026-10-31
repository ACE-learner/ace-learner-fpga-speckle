#include <iostream>
#include <cstdio>
#include"debug.h"
#pragma GCC optimize(3,"Ofast","inline")
using namespace std;

/* 用 FatFS 读取 yolo_test\img_num.txt（C stdio 的 fopen 在本工程不可用） */
static int read_img_num(const char* path, int defv)
{
    FIL f;
    FRESULT rc = f_open(&f, path, FA_READ);
    if (rc != FR_OK) {
        printf("img_num.txt not found (rc=%d), use default %d\n", rc, defv);
        return defv;
    }
    char buf[32];
    UINT br = 0;
    f_read(&f, buf, sizeof(buf) - 1, &br);
    f_close(&f);
    int n = 0;
    for (UINT i = 0; i < br; i++) {
        if (buf[i] >= '0' && buf[i] <= '9') n = n * 10 + (buf[i] - '0');
    }
    if (n <= 0) return defv;
    if (n > 200) n = 200;
    return n;
}

int main()
{
    string weight_dir="yolov4_tiny_weights";
    string ref_dir="yolo_test";

    cout << "Yolo4 Tiny Test" << endl;
    int sdi = SD_Init();
    printf("SD_Init = %d\n", sdi);

    int img_num = read_img_num("yolo_test\\img_num.txt", 54);
    cout << "image num = " << img_num << endl;

    yolo_test(weight_dir, ref_dir, img_num);
    return 0;
}
