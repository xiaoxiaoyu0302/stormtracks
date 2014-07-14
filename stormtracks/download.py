import os
import urllib
import tarfile
import shutil

from load_settings import settings

C20_FULL_DATA_DIR = settings.C20_FULL_DATA_DIR
C20_MEAN_DATA_DIR = settings.C20_MEAN_DATA_DIR
DATA_DIR = settings.DATA_DIR

def download_file(url, output_dir, path=None):
    if path == None:
	path = os.path.join(output_dir, url.split('/')[-1])

    print(path)
    if os.path.exists(path):
        print('Already exists, skipping')
    else:
        urllib.urlretrieve(url, path)

    return path


def download_ibtracs():
    url = 'ftp://eclipse.ncdc.noaa.gov/pub/ibtracs/v03r05/archive/ibtracs_v03r05_dataset_184210_201305.tar.gz'
    data_dir = DATA_DIR
    if not os.path.exists(data_dir):
	os.makedirs(data_dir)
    # tarball will be downloaded to data_dir.
    path = download_file(url, data_dir)
    # it will be decompressed to data_dir/ibtracs
    decompress_file(path)

def download_mean_c20_range(start_year, end_year):
    """Downloads mean values for prmsl, u and v in a given range"""
    for year in range(start_year, end_year + 1):
	download_mean_c20(year)

def download_full_c20_range(start_year, end_year):
    """Downloads each ensemble member's values for prmsl, u and v in a given range"""
    for year in range(start_year, end_year + 1):
	download_full_c20(year)

def download_mean_c20(year):
    """Downloads mean values for prmsl, u and v"""
    y = str(year)
    data_dir_tpl = os.path.join(C20_MEAN_DATA_DIR, y)
    if not os.path.exists(data_dir):
	os.makedirs(data_dir)

    urls = ['ftp://ftp.cdc.noaa.gov/Datasets/20thC_ReanV2/monolevel/prmsl.%s.nc',
	    'ftp://ftp.cdc.noaa.gov/Datasets/20thC_ReanV2/monolevel/uwnd.sig995.%s.nc',
	    'ftp://ftp.cdc.noaa.gov/Datasets/20thC_ReanV2/monolevel/vwnd.sig995.%s.nc',
	    ]
    print(year)
    for url in urls:
	download_file(url%y, data_dir)

    compress_dir(data_dir)
    print('removing dir %s'%data_dir)
    shutil.rmtree(data_dir)

def download_full_c20(year):
    """Downloads each ensemble member's values for prmsl, u and v"""
    y = str(year)
    data_dir = os.path.join(C20_FULL_DATA_DIR, y)

    if not os.path.exists(data_dir):
	os.makedirs(data_dir)

    urls = ['http://portal.nersc.gov/pydap/20C_Reanalysis_ensemble/analysis/u9950/u9950_%s.nc',
            'http://portal.nersc.gov/pydap/20C_Reanalysis_ensemble/analysis/v9950/v9950_%s.nc',
            'http://portal.nersc.gov/pydap/20C_Reanalysis_ensemble/analysis/prmsl/prmsl_%s.nc',
	    ]
    print(year)
    for url in urls:
	download_file(url%y, data_dir)

    # These files are incompressible (already compressed I guess)

    #compress_dir(data_dir)
    #print('removing dir %s'%data_dir)
    #shutil.rmtree(data_dir)

def compress_dir(data_dir):
    compressed_file = data_dir + '.bz2'
    print('compressing to %s'%compressed_file)
    tar = tarfile.open(compressed_file, 'w:bz2')
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            tar.add(os.path.join(root, file))
    tar.close()

def decompress_file(compressed_file):
    print('decompressing %s'%compressed_file)
    tar = tarfile.open(compressed_file)
    tar.extractall(os.path.dirname(compressed_file))
    tar.close()


if __name__ == "__main__":
    download_ibtracs()
    # Will take a while, each year is 4.2GB of data.
    download_full_c20(2005)