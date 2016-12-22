#from req import Service
class GroupConst:
    DEFAULT_GROUP = 'normal_user'
    KERNEL_GROUP = 'kernel'
class GroupService:
    DEFAULT_GROUP = 'normal_user'
    KERNEL_GROUP = 'kernel'
    def __init__(self,db,rs):
        self.db = db
        self.rs = rs
        GroupService.inst = self
    def add_group(self,gname,gtype,gclas):
        glist = yield from self.list_group()
        if gname in glist:
            return 'Eexist'
        cur = yield self.db.cursor()
        yield cur.execute('INSERT INTO "group" '
            '("group_name","group_type","group_class") '
            'VALUES (%s,%s,%s) ;'
            ,(gname,gtype,gclas))
        return None
    def del_group(self,gname):
        glist = yield from self.list_group()
        if gname not in glist:
            return 'Eexist'
        cur = yield self.db.cursor()
        yield cur.execute('DELETE FROM "group" '
            'WHERE "group"."group_name"=%s;'
            ,(gname,))
        gacct = yield from self.list_acct_in_group(gname)
        for acct in gacct:
            err = yield from self.set_acct_group(acct['acct_id'],self.DEFAULT_GROUP)
        return None
    def list_group(self):
        cur = yield self.db.cursor()
        yield cur.execute('SELECT '
            '"group"."group_name" '
            'FROM "group";'
            )
        glist = []
        for (gname,) in cur:
            glist.append(str(gname))
        return glist
    def list_acct_in_group(self,gname):
        cur = yield self.db.cursor()
        yield cur.execute('SELECT '
            '"account"."acct_id",'
            '"account"."name" '
            'FROM "account" '
            'WHERE "account"."group" = %s '
            'ORDER BY "account"."acct_id";'
            ,(gname,))
        acct_list = []
        for (acct_id,acct_name) in cur:
            acct_list.append({
                'acct_id':int(acct_id),
                'acct_name':str(acct_name)
                })
        return acct_list
    def group_of_acct(self,acct_id):
        cur = yield self.db.cursor()
        yield cur.execute('SELECT '
            '"account"."group" '
            'FROM "account" '
            'WHERE "account"."acct_id"=%s;'
            ,(acct_id,))
        (group,) = cur.fetchone()
        return group
    def set_acct_group(self,acct_id,gname):
        glist = yield from self.list_group()
        if gname not in glist:
            return 'Eexist'
        cur = yield self.db.cursor()
        yield cur.execute('SELECT '
            '"group"."group_type","group"."group_class" '
            'FROM "group" '
            'WHERE "group"."group_name"=%s;'
            ,(gname,))
        (gtype,gclas) = cur.fetchone()

        yield cur.execute('UPDATE "account" '
            'SET "group"=%s,"acct_type"=%s,"class"=\'{%s}\' '
            'where "account"."acct_id"=%s;'
            ,(gname,gtype,gclas,acct_id))

        yield cur.execute('REFRESH MATERIALIZED VIEW test_valid_rate;')
        self.rs.delete('account@%d'%acct_id)
        self.rs.delete('acctlist')
        self.rs.delete('prolist')
        self.rs.delete('rate@kernel_True')
        self.rs.delete('rate@kernel_False')
        return None
    def _update_group(self,gname,gtype,gclas):
        cur = yield self.db.cursor()
        yield cur.execute('UPDATE "group" '
            'SET "group_type"=%s,"group_class"=%s '
            'WHERE "group_name"=%s;'
            ,(gtype,gclas,gname))
        if cur.rowcount != 1:
            return 'Eexist'
        return None
    def update_group(self,gname,gtype,gclas):
        
        glist = yield from self.list_group()
        if gname not in glist:
            return 'Eexist'
        err = yield from self._update_group(gname,int(gtype),int(gclas))
        if err:
            return err
        gacct = yield from self.list_acct_in_group(gname)
        for acct in gacct:
            err = yield from self.set_acct_group(acct['acct_id'],gname)
        return None

