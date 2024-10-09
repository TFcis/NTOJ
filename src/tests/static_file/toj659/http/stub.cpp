#include <iostream>
using namespace std;

int answer();
long long N, qcnt, ans;

int query(int k)
{
    qcnt++;
    if(k < N)
        return -1;
    else if(k > N)
        return 1;
    return 0;
}

int main()
{
    cin >> N;
    ans = answer();
    if (qcnt > 32)
    	cout << "Wrong Answer: too many query calls";
    else if (ans != N)
        cout << "Wrong Answer: output isn't correct";
    else 
		cout << "Accepted\n";
        
}
