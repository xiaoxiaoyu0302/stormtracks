import os
import time
import datetime as dt

import numpy as np
from netCDF4 import Dataset
from scipy.interpolate import interp1d
import scipy.ndimage as ndimage

from utils.c_wrapper import cvort, cvort4
from utils.utils import find_extrema 
from load_settings import settings

DATA_DIR = settings.C20_FULL_DATA_DIR

EARTH_RADIUS = 6371
EARTH_CIRC = EARTH_RADIUS * 2 * np.pi

class C20Data(object):
    def __init__(self, 
                start_year, ensemble=True, smoothing=False, verbose=True,
                upscaling=False):
        self._year = start_year
        self.dx = None
        self.date = None
        self.smoothing = smoothing
        self.ensemble = ensemble
        self.verbose = verbose
        self.upscaling = upscaling

        self.debug = False

        self.load_datasets(self._year)

    def __say(self, text):
        if self.verbose:
            print(text)

    def set_year(self, year):
        self._year = year
        self.close_datasets()
        self.load_datasets(self._year)

    def close_datasets(self):
        self.nc_prmsl.close()
        self.nc_u.close()
        self.nc_v.close()

    def load_datasets(self, year):
        y = str(year)
        if not self.ensemble:
            self.nc_prmsl = Dataset('{0}/{0}/prmsl.{0}.nc'.format(y))
            self.nc_u = Dataset('data/c20/{0}/uwnd.sig995.{0}.nc'.format(y))
            self.nc_v = Dataset('data/c20/{0}/vwnd.sig995.{0}.nc'.format(y))
            start_date = dt.datetime(1800, 1, 1)
            hours_since_1800 = self.nc_prmsl.variables['time'][:]
            self.dates = np.array([start_date + dt.timedelta(hs / 24.) for hs in hours_since_1800])
        else:
            self.nc_prmsl = Dataset('{0}/{1}/prmsl_{1}.nc'.format(DATA_DIR, y))
            self.nc_u = Dataset('{0}/{1}/u9950_{1}.nc'.format(DATA_DIR, y))
            self.nc_v = Dataset('{0}/{1}/v9950_{1}.nc'.format(DATA_DIR, y))
            start_date = dt.datetime(1, 1, 1)
            hours_since_JC = self.nc_prmsl.variables['time'][:]
            self.dates = np.array([start_date + dt.timedelta(hs / 24.) - dt.timedelta(2) for hs in hours_since_JC])
            self.number_enseble_members = self.nc_prmsl.variables['prmsl'].shape[1]

        self.lons = self.nc_prmsl.variables['lon'][:]
        self.lats = self.nc_prmsl.variables['lat'][:]

        dlon = self.lons[2] - self.lons[0]

        # N.B. array as dx varies with lat.
        self.dx = (dlon * np.cos(self.lats * np.pi / 180) * EARTH_CIRC)
        self.dy = (self.lats[0] - self.lats[2]) * EARTH_CIRC

        self.f_lon = interp1d(np.arange(0, 180), self.lons)
        self.f_lat = interp1d(np.arange(0, 91), self.lats)

    def first_date(self, ensemble_member=0, ensemble_mode='member'):
        return self.set_date(self.dates[0], ensemble_member, ensemble_mode)

    def next_date(self, ensemble_member=0, ensemble_mode='member'):
        index = np.where(self.dates == self.date)[0][0]
        if index < len(self.dates):
            date = self.dates[index + 1]
            return self.set_date(date, ensemble_member, ensemble_mode)
        else:
            return None

    def prev_date(self, ensemble_member=0, ensemble_mode='member'):
        index = np.where(self.dates == self.date)[0][0]
        if index > 0:
            date = self.dates[index - 1]
            return self.set_date(date, ensemble_member, ensemble_mode)
        else:
            return None

    def set_date(self, date, ensemble_member=0, ensemble_mode='member'):
        if date != self.date or ensemble_member != self.ensemble_member:
            try:
                self.__say("Setting date to {0}".format(date))
                index = np.where(self.dates == date)[0][0]
                self.date = date
                self.ensemble_member = ensemble_member
                self.ensemble_mode = ensemble_mode
                if not self.ensemble:
                    self.__process_data(index)
                else:
                    self.__process_ensemble_data(index, ensemble_member, ensemble_mode)
            except:
                self.date = None
                self.ensemble_member = None
                self.ensemble_mode = None
                raise
        return date

    def cvorticity(self, u, v):
        vort = np.zeros_like(u)
        cvort(u, v, u.shape[0], u.shape[1], self.dx, self.dy, vort)
        return vort

    def cvorticity4(self, u, v):
        '''Taken from Walsh's Algorithm'''
        vort = np.zeros_like(u)
        cvort4(u, v, u.shape[0], u.shape[1], self.dx, self.dy, vort)
        return vort

    def vorticity(self, u, v):
        vort = np.zeros_like(u)

        for i in range(1, u.shape[0] - 1):
            for j in range(1, u.shape[1] - 1):
                du_dy = (u[i + 1, j] - u[i - 1, j])/ self.dy
                dv_dx = (v[i, j + 1] - v[i, j - 1])/ self.dx[i]

                vort[i, j] = dv_dx - du_dy
        return vort

    def fourth_order_vorticity(self, u, v):
        '''Taken from Walsh's Algorithm'''
        vort = np.zeros_like(u)

        for i in range(2, u.shape[0] - 2):
            for j in range(2, u.shape[1] - 2):
                du_dy1 = 2 * (u[i + 1, j] - u[i - 1, j]) / (3 * self.dy)
                du_dy2 = (u[i + 2, j] - u[i - 2, j]) / (12 * self.dy)
                du_dy = du_dy1 - du_dy2

                dv_dx1 = 2 * (v[i, j + 1] - v[i, j - 1]) / (3 * self.dx[i])
                dv_dx2 = (v[i, j + 2] - v[i, j - 2]) / (12 * self.dx[i])
                dv_dx = dv_dx1 - dv_dx2

                vort[i, j] = dv_dx - du_dy
        return vort

    def __process_data(self, i):
        start = time.time()
        self.psl = self.nc_prmsl.variables['prmsl'][i]

        # TODO: Why minus sign?
        self.u = - self.nc_u.variables['uwnd'][i]
        self.v = self.nc_v.variables['vwnd'][i]

        end = time.time()
        self.__say('  Loaded psl, u, v in {0}'.format(end - start))

        start = time.time()
        self.vort  = self.vorticity(self.u, self.v, self.lons, self.lats)
        self.vort4 = self.fourth_order_vorticity(self.u, self.v, self.lons, self.lats)
        end = time.time()
        self.__say("  Calc'd vorticity in {0}".format(end - start))

        start = time.time()
        e, index_pmaxs, index_pmins = find_extrema(self.psl)
        self.pmins = [(self.psl[pmin[0], pmin[1]], (self.lons[pmin[1]], self.lats[pmin[0]])) for pmin in index_pmins]
        e, index_vmaxs, index_vmins = find_extrema(self.vort)
        self.vmaxs = [(self.vort[vmax[0], vmax[1]], (self.lons[vmax[1]], self.lats[vmax[0]])) for vmax in index_vmaxs]

        end = time.time()
        self.__say('  Found maxima/minima in {0}'.format(end - start))

        if self.smoothing:
            start = time.time()
            self.smoothed_vort = ndimage.filters.gaussian_filter(self.vort, 1, mode='nearest')
            e, index_svmaxs, index_svmins = find_extrema(self.smoothed_vort)
            self.smoothed_vmaxs = [(self.smoothed_vort[svmax[0], svmax[1]], (self.lons[svmax[1]], self.lats[svmax[0]])) for svmax in index_svmaxs]
            end = time.time()
            self.__say('  Smoothed vorticity in {0}'.format(end - start))
        

    def __process_ensemble_data(self, i, ensemble_member, ensemble_mode):
        if ensemble_mode not in ['member', 'mean', 'full', 'diff']:
            raise Exception('ensemble_mode should be one of member, mean, diff or full')

        if ensemble_mode == 'member':
            if ensemble_member < 0 or ensemble_member >= self.number_enseble_members:
                raise Exception('Ensemble member must be be between 0 and {0}'.format(self.number_enseble_members))

        start = time.time()
        if ensemble_mode == 'member':
            self.psl = self.nc_prmsl.variables['prmsl'][i, ensemble_member]
        elif ensemble_mode == 'mean':
            self.psl = self.nc_prmsl.variables['prmsl'][i].mean(axis=0)
        elif ensemble_mode == 'diff':
            self.psl = self.nc_prmsl.variables['prmsl'][i].max(axis=0) - self.nc_prmsl.variables['prmsl'][i].min(axis=0)
        elif ensemble_mode == 'full':
            self.psl = self.nc_prmsl.variables['prmsl'][i]

        # TODO: Why minus sign?
        if ensemble_mode == 'member':
            self.u = - self.nc_u.variables['u9950'][i, ensemble_member]
            self.v = self.nc_v.variables['v9950'][i, ensemble_member]
        elif ensemble_mode == 'mean':
            self.u = - self.nc_u.variables['u9950'][i].mean(axis=0)
            self.v = self.nc_v.variables['v9950'][i].mean(axis=0)
        elif ensemble_mode == 'diff':
            self.u =  - self.nc_u.variables['u9950'][i].max(axis=0) - self.nc_u.variables['u9950'][i].min(axis=0) 
            self.v =  self.nc_v.variables['v9950'][i].max(axis=0) - self.nc_v.variables['v9950'][i].min(axis=0)
        elif ensemble_mode == 'full':
            self.u = - self.nc_u.variables['u9950'][i]
            self.v = self.nc_v.variables['v9950'][i]

        end = time.time()
        self.__say('  Loaded psl, u, v in {0}'.format(end - start))

        start = time.time()
        if ensemble_mode in ['member', 'mean', 'diff']:
            self.vort  = self.cvorticity(self.u, self.v)
            self.vort4 = self.cvorticity4(self.u, self.v)
        else:
            vort = []
            vort4 = []
            for i in range(self.number_enseble_members):
                vort.append(self.cvorticity(self.u[i], self.v[i]))
                vort4.append(self.cvorticity4(self.u[i], self.v[i]))
            self.vort = np.array(vort)
            self.vort4 = np.array(vort4)

        end = time.time()
        self.__say("  Calc'd c vorticity in {0}".format(end - start))

        if self.debug:
            start = time.time()
            vort  = self.vorticity(self.u, self.v)
            vort4 = self.fourth_order_vorticity(self.u, self.v)
            end = time.time()
            self.__say("  Calc'd vorticity in {0}".format(end - start))

            if abs((self.vort - vort).max()) > 1e-10:
                raise Exception('Difference between python/c vort calc')

            if abs((self.vort4 - vort4).max()) > 1e-10:
                raise Exception('Difference between python/c vort4 calc')

        if ensemble_mode in ['member', 'mean', 'diff']:
            e, index_pmaxs, index_pmins = find_extrema(self.psl)
            self.pmins = [(self.psl[pmin[0], pmin[1]], (self.lons[pmin[1]], self.lats[pmin[0]])) for pmin in index_pmins]

            e, index_vmaxs, index_vmins = find_extrema(self.vort)
            self.vmaxs = [(self.vort[vmax[0], vmax[1]], (self.lons[vmax[1]], self.lats[vmax[0]])) for vmax in index_vmaxs]

            e, index_v4maxs, index_v4mins = find_extrema(self.vort4)
            self.v4maxs = [(self.vort4[v4max[0], v4max[1]], (self.lons[v4max[1]], self.lats[v4max[0]])) for v4max in index_v4maxs]
        else:
            self.pmins = []
            self.vmaxs = []
            self.v4maxs = []

            for i in range(self.number_enseble_members):
                e, index_pmaxs, index_pmins = find_extrema(self.psl[i])
                self.pmins.append([(self.psl[i, pmin[0], pmin[1]], (self.lons[pmin[1]], self.lats[pmin[0]])) for pmin in index_pmins])

                e, index_vmaxs, index_vmins = find_extrema(self.vort[i])
                self.vmaxs.append([(self.vort[i, vmax[0], vmax[1]], (self.lons[vmax[1]], self.lats[vmax[0]])) for vmax in index_vmaxs])

                e, index_v4maxs, index_v4mins = find_extrema(self.vort4[i])
                self.v4maxs.append([(self.vort4[i, v4max[0], v4max[1]], (self.lons[v4max[1]], self.lats[v4max[0]])) for v4max in index_v4maxs])

        end = time.time()
        self.__say('  Found maxima/minima in {0}'.format(end - start))
        if self.smoothing:
            start = time.time()
            self.smoothed_vort = ndimage.filters.gaussian_filter(self.vort, 1, mode='nearest')
            e, index_svmaxs, index_svmins = find_extrema(self.smoothed_vort)
            self.smoothed_vmaxs = [(self.smoothed_vort[svmax[0], svmax[1]], (self.lons[svmax[1]], self.lats[svmax[0]])) for svmax in index_svmaxs]
            end = time.time()
            self.__say('  Smoothed vorticity in {0}'.format(end - start))

        if self.upscaling:
            start = time.time()
            self.up_lons, self.up_lats, self.up_vort  = upscale_field(self.lons, self.lats, self.vort)
            e, index_upvmaxs, index_upvmins = find_extrema(self.up_vort)
            self.up_vmaxs = [(self.up_vort[upvmax[0], upvmax[1]], (self.up_lons[upvmax[1]], self.up_lats[upvmax[0]])) for upvmax in index_upvmaxs]
            end = time.time()
            self.__say('  Upscaled vorticity in {0}'.format(end - start))


class GlobalEnsembleMember(object):
    '''
    Wrapper around a C20Data object that holds state of which ensemble member
    is currently being analysed
    '''
    def __init__(self, c20data, ensemble_member=0):
        self.c20data = c20data
        self.dates = c20data.dates
        self.lons = c20data.lons
        self.lats = c20data.lats

        self.date = None
        self.cyclones_by_date = {}
        self.ensemble_member = ensemble_member

    def set_year(self, year):
        self.year = year
        self.c20data.set_year(year)
        self.dates = self.c20data.dates

    def set_date(self, date):
        if date != self.date:
            self.date = date
            self.c20data.set_date(date, self.ensemble_member)