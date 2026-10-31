/* 
 * sd_io.h
 */
#include "ff.h"
#include "xparameters.h"
#include "xdevcfg.h"
#include<cstdlib>
#include<cstdio>
#include<string>
#include<cmath>
#include<iostream>

#define SCALE 512
typedef short data_t;
using namespace std;

static FATFS fatfs;

int SD_Init();

void write_data(string filename,data_t* x,int length);

void read_params(string filename,data_t* x,int length);





