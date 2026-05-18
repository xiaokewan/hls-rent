void mm(int A[16], int B[16], int C[1]) {
#pragma HLS ARRAY_PARTITION variable=A complete dim=1
#pragma HLS ARRAY_PARTITION variable=B complete dim=1
  int acc = 0;
#pragma HLS PIPELINE II=1
  for (int k = 0; k < 2; ++k) {
#pragma HLS UNROLL factor=2
    for (int u = 0; u < 2; ++u) {
      int a = A[k * 2 + u];
      int b = B[k * 2 + u];
      acc += a * b;
    }
  }
  C[0] = acc;
}
