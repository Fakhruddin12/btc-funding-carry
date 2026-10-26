"""Write complete tables atomically, with row-count verification."""
import os
import pandas as pd


def save_frame(frame,path,index=True):
    temporary=path.with_suffix('.building.csv')
    with temporary.open('w') as stream:
        frame.to_csv(stream,index=index)
        stream.flush();os.fsync(stream.fileno())
    if len(frame.columns) and len(pd.read_csv(temporary))!=len(frame):
        raise ValueError(f'Incomplete output: {path.name}')
    os.replace(temporary,path)
