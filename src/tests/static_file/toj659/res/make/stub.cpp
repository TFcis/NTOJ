#include <iostream>
using namespace std;

int answer();

class Interaction
{
	private:
		long long N, qcnt;
	public:
		int query(int k)
		{
    		qcnt++;
    		if(k < N)
    		    return -1;
    		else if(k > N)
    		    return 1;
    		return 0;
		}
		void setN(long long _N)
		{
			N = _N;
		}
		bool check(long long _N)
		{
			if (qcnt <= 32 && _N == N)
				return true;
			return false;
		}
};

long long ans;
Interaction interaction;

int query(int k)
{
   	return interaction.query(k);
}


int main()
{
    long long N;
    if(!(cin >> N))
    {
        cout << "Wrong Answer: Corrupted Input\n";
        return 0;
    }
    interaction.setN(N);
    N ^= 0x5f50192;
    
    ans = answer();
    
    if (interaction.check(ans))
        cout << "Accepted, Answer: " << N << "\n";
    else
        cout << "Wrong Answer: tried too many times or guessed " << ans << '\n';
}
