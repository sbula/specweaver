from specweaver.workspace.store import Base

print([c.name for c in Base.metadata.tables['projects'].columns])
