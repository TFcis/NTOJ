class ContestService:
    def __init__(self, db, rs):
        self.db = db
        self.rs = rs
        ContestService.inst = self
