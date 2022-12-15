from . import *
CRS = {
    'census'  : 'EPSG:4269'  , # degrees - used by Census
    'bigquery': 'EPSG:4326'  , # WSG84 - used by Bigquery
    'area'    : 'ESRI:102003', # meters
    'length'  : 'ESRI:102005', # meters
}

@dataclasses.dataclass
class Github():
    token: str
    repo : str
    user : str = 'drscook'
    email: str = 'scook@tarleton.edu'
    base : str = '/content/'

    def __post_init__(self):
        os.popen(f'git config --global user.email {self.email}')
        os.popen(f'git config --global user.name {self.user}')
        self.url = f'https://{self.token}@github.com/{self.user}/{self.repo}'
        self.path = self.base + self.repo


    def pull(self):
        cwd = os.getcwd()
        os.chdir(self.base)
        if os.system(f'git clone {self.url}') != 0:
            os.chdir(self.path)
            os.popen(f'git remote set-url origin {self.url}')
            print(os.popen(f'git pull').read())
        os.chdir(cwd)

    def push(self, msg='changes'):
        cwd = os.getcwd()
        os.chdir(self.path)
        os.popen(f'git remote set-url origin {self.url}')
        print(os.popen(f'git add .').read())
        print(os.popen(f'git commit -m {msg}').read())
        print(os.popen(f'git push').read())
        os.chdir(cwd)

        
def listify(X):
    """Turns almost anything into a list"""
    if isinstance(X, list):
        return X
    elif (X is None) or (X is np.nan) or (X==''):
        return []
    elif isinstance(X, str):
        return [X]
    else:
        try:
            return list(X)
        except:
            return [X]

def join(parts, sep=', '):
    """ join list into single string """
    return sep.join([str(p) for p in listify(parts)])

def subquery(qry, indents=1):
    """indent query for inclusion as subquery"""
    s = '\n' + indents * '    '
    return qry.strip(';\n ').replace('\n', s)  # strip leading/trailing whitespace and indent all but first line

def make_select(cols, indents=1, sep=',\n', tbl=None):
    """ useful for select statements """
    cols = listify(cols)
    if tbl is not None:
        cols = [f'{tbl}.{x}' for x in cols]
    qry = join(cols, sep)
    return subquery(qry, indents)

def to_numeric(ser):
    """converts columns to small numeric dtypes when possible"""
    dt = str(ser.dtype)
    if  dt in ['geometry', 'timestamp'] or dt[0].isupper():
        return ser
    else:
        return pd.to_numeric(ser, errors='ignore', downcast='integer')  # cast to numeric datatypes where possible

def prep(df, fix_names=True):
    """prep dataframes"""
    idx = len(df.index.names)
    df = df.reset_index()
    if fix_names:
        df.columns = [c.strip().lower() for c in df.columns]
    return df.apply(to_numeric).convert_dtypes().set_index(df.columns[:idx].tolist())

def transform_labeled(trans, df):
    """apply scikit-learn tranformation and return dataframe with appropriate column names and index"""
    return prep(pd.DataFrame(trans.fit_transform(df), columns=trans.get_feature_names_out(), index=df.index))

def decade(year):
    return int(year) // 10 * 10

class BQ():
    def __init__(self, project_id):
        from google.colab import auth
        from google.cloud.bigquery import Client
        auth.authenticate_user()
        self.client = Client(project=project_id)
  
    def run_qry(self, qry):
        return self.client.query(qry).result()

    def qry_to_df(self, qry):
        res = self.run_qry(qry)
        if res.total_rows > 0:
          df = prep(res.to_dataframe())
          if 'geometry' in df.columns:
              geo = gpd.GeoSeries.from_wkt(df['geometry'], crs=CRS['bigquery'])
              df = gpd.GeoDataFrame(df, geometry=geo)
        return df

    def qry_to_tbl(self, qry, tbl, overwrite=False):
        if not self.get_tbl(tbl, overwrite=overwrite):
            qry = f"""
create table {tbl} as (
    {subquery(qry)}
)"""
            self.client.create_dataset(tbl.split('.')[0], exists_ok=True)
            self.run_qry(qry)
        return tbl


    def del_tbl(self, tbl):
        self.client.delete_table(tbl, not_found_ok=True)

    def del_ds(self, ds):
        self.client.delete_dataset(ds, not_found_ok=True)

    def copy_ds(self, curr, targ):
        self.del_ds(targ)
        self.client.create_dataset(targ)
        for t in self.client.list_tables(curr):
            self.client.copy_table(t, f'{targ}.{t.table_id}')

    def get_tbl(self, tbl, overwrite=False):
        if overwrite:
            self.del_tbl(tbl)
        try:
            return self.client.get_table(tbl)
        except:
            return False

    def get_cols(self, tbl):
        t = self.get_tbl(tbl) 
        if t:
            t = [s.name.lower() for s in t.schema]
        return t


