/* Day 12 - ARM NEON: scalar vs. 4-lane SIMD dot product and ReLU. */

#include <arm_neon.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define N (1 << 20)
#define REPEAT 300
#define RELU_REPEAT 300

static double elapsed_ms(clock_t start, clock_t end) {
  return (double)(end - start) * 1000.0 / CLOCKS_PER_SEC;
}

/* Disable compiler auto-vectorization here: this is the scalar baseline. */
__attribute__((noinline)) static float dot_scalar(const float *a,
                                                   const float *b, int n) {
  float sum = 0.0f;
#pragma clang loop vectorize(disable)
  for (int i = 0; i < n; ++i) {
    sum += a[i] * b[i];
  }
  return sum;
}

/* Four float32 values are loaded and accumulated per iteration. */
__attribute__((noinline)) static float dot_neon(const float *a,
                                                 const float *b, int n) {
  float32x4_t vector_sum = vdupq_n_f32(0.0f);
  int i = 0;

  for (; i <= n - 4; i += 4) {
    float32x4_t va = vld1q_f32(a + i);
    float32x4_t vb = vld1q_f32(b + i);
    vector_sum = vfmaq_f32(vector_sum, va, vb);
  }

  float sum = vaddvq_f32(vector_sum);
  for (; i < n; ++i) {
    sum += a[i] * b[i];
  }
  return sum;
}

__attribute__((noinline)) static void relu_scalar(float *data, int n) {
#pragma clang loop vectorize(disable)
  for (int i = 0; i < n; ++i) {
    data[i] = data[i] > 0.0f ? data[i] : 0.0f;
  }
}

__attribute__((noinline)) static void relu_neon(float *data, int n) {
  const float32x4_t zero = vdupq_n_f32(0.0f);
  int i = 0;

  for (; i <= n - 4; i += 4) {
    float32x4_t value = vld1q_f32(data + i);
    vst1q_f32(data + i, vmaxq_f32(value, zero));
  }
  for (; i < n; ++i) {
    data[i] = data[i] > 0.0f ? data[i] : 0.0f;
  }
}

static void fill_inputs(float *a, float *b, int n) {
  for (int i = 0; i < n; ++i) {
    a[i] = (float)((i % 97) - 48) * 0.02f;
    b[i] = (float)((i % 71) - 35) * 0.03f;
  }
}

int main(void) {
  float *a = malloc(sizeof(float) * N);
  float *b = malloc(sizeof(float) * N);
  float *relu_a = malloc(sizeof(float) * N);
  float *relu_b = malloc(sizeof(float) * N);
  volatile float checksum = 0.0f;

  if (!a || !b || !relu_a || !relu_b) {
    fprintf(stderr, "Memory allocation failed.\n");
    free(a); free(b); free(relu_a); free(relu_b);
    return 1;
  }

  fill_inputs(a, b, N);
  for (int i = 0; i < N; ++i) {
    relu_a[i] = a[i];
    relu_b[i] = a[i];
  }

  float scalar_once = dot_scalar(a, b, N);
  float neon_once = dot_neon(a, b, N);
  printf("=== Day 12: ARM NEON Vectorization ===\n");
  printf("Vector type: float32x4_t (4 x float32 per 128-bit register)\n");
  printf("Elements: %d, repeats: %d\n", N, REPEAT);
  printf("Dot result - scalar: %.4f, NEON: %.4f, difference: %.6f\n",
         scalar_once, neon_once, scalar_once - neon_once);

  clock_t start = clock();
  for (int i = 0; i < REPEAT; ++i) {
    checksum += dot_scalar(a, b, N);
    /* Prevent loop-invariant result hoisting by the optimizing compiler. */
    a[(i * 7919) & (N - 1)] += 0.000001f;
  }
  clock_t scalar_end = clock();

  fill_inputs(a, b, N);
  for (int i = 0; i < REPEAT; ++i) {
    checksum += dot_neon(a, b, N);
    a[(i * 7919) & (N - 1)] += 0.000001f;
  }
  clock_t neon_end = clock();

  double scalar_ms = elapsed_ms(start, scalar_end);
  double neon_ms = elapsed_ms(scalar_end, neon_end);
  printf("Scalar dot: %.2f ms\n", scalar_ms);
  printf("NEON dot  : %.2f ms\n", neon_ms);
  printf("Speedup   : %.2fx\n", scalar_ms / neon_ms);

  for (int i = 0; i < N; ++i) {
    relu_a[i] = a[i];
    relu_b[i] = a[i];
  }
  clock_t relu_start = clock();
  for (int i = 0; i < RELU_REPEAT; ++i) relu_scalar(relu_a, N);
  clock_t relu_scalar_end = clock();
  for (int i = 0; i < RELU_REPEAT; ++i) relu_neon(relu_b, N);
  clock_t relu_neon_end = clock();
  double relu_scalar_ms = elapsed_ms(relu_start, relu_scalar_end);
  double relu_neon_ms = elapsed_ms(relu_scalar_end, relu_neon_end);

  printf("Scalar ReLU: %.2f ms\n", relu_scalar_ms);
  printf("NEON ReLU  : %.2f ms\n", relu_neon_ms);
  printf("ReLU speedup: %.2fx\n", relu_scalar_ms / relu_neon_ms);
  printf("ReLU check: scalar[0]=%.2f, NEON[0]=%.2f\n", relu_a[0], relu_b[0]);
  printf("Checksum (prevents optimization): %.2f\n", checksum);

  free(a); free(b); free(relu_a); free(relu_b);
  return 0;
}
