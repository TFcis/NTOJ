#include <bits/stdc++.h>
using namespace std;

int main() {
	long double Answer, Output;
	FILE *ansf = fdopen(2, "r");

	scanf("%Lf", &Output);
	fscanf(ansf, "%Lf", &Answer);

	long double Ae = abs(Answer - Output);
	long double Re = Ae / Answer;

	if (Ae <= 0.000001 || Re <= 0.000001) {
		return 0;
	} else {
		return -1;
	}
}
