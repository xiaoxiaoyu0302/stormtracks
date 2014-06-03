from argparse import ArgumentParser
import datetime as dt

from netCDF4 import Dataset
import numpy as np
import pylab as plt
from scipy.interpolate import interp1d

from cyclone import Cyclone, Isobar, Pos

def main(args):
    #nc = Dataset('processed_data/c20_200510.nc')
    #nc = Dataset('processed_data/c20_200508.nc')
    nc_prmsl = Dataset('data/20C_2005_Wilma/prmsl.2005.nc')
    nc_u = Dataset('data/20C_2005_Wilma/uwnd.2005.nc')
    nc_v = Dataset('data/20C_2005_Wilma/vwnd.2005.nc')
    lat = nc_prmsl.variables['lat']
    lon = nc_prmsl.variables['lon']

    f_lon = interp1d(np.arange(0, 180), lon)
    f_lat = interp1d(np.arange(0, 91), lat)


    plt.ioff()
    daily_candidate_cyclones = []
    daily_all_cyclones = []
    daily_psls = []
    daily_uws = []
    daily_vws = []
    run_count = 0
    hours_since_1800 = nc_prmsl.variables['time'][:]
    start_date = dt.datetime(1800, 1, 1)
    all_times = np.array([start_date + dt.timedelta(hs / 24.) for hs in hours_since_1800])
    times = []
    for i in range(int(args.start), int(args.end)):
        times.append(all_times[i])
        print(all_times[i])
        psl = nc_prmsl.variables['prmsl'][i]

        #import ipdb; ipdb.set_trace()
        u = nc_u.variables['uwnd'][i, 0]
        v = nc_v.variables['vwnd'][i, 0]
        vort = vorticity(u, v)

        e, maxs, mins = find_extrema(psl)
        if False:
            plt.clf()
            plt.figure(1)
            plt.imshow(psl[::-1], interpolation='nearest')
            #vor = voronoi(e, maxs, mins)
            plt.figure(2)
            plt.imshow(e[::-1], interpolation='nearest')
            #plt.figure(3)
            #plt.imshow(vor[::-1], interpolation='nearest')
            plt.figure(4)
            plt.quiver(u, v)
            plt.figure(5)
            plt.imshow(vort[::-1], interpolation='nearest')


        pressures = np.arange(94000, 103000, 300)
        cn = plt.contour(psl, levels=pressures)

        contours = get_contour_verts(cn)

        min_cs = []
        cyclones = {}
        for min_point in mins:
            cyclones[min_point] = Cyclone(min_point[1], min_point[0], lon, lat, [])

        for pressure, contour_set in zip(pressures, contours):
            for contour in contour_set:
                isobar = Isobar(pressure, contour, lon, lat, f_lon, f_lat)
                contained_points = []
                for min_point in mins:
                    if isobar.contains(Pos(min_point[1], min_point[0])):
                        contained_points.append(min_point)
                if len(contained_points) == 1:
                    cyclones[contained_points[0]].isobars.append(isobar)
                if len(contained_points) > 1:
                    prev_pressure = None
                    is_found = True

                    for i in range(len(contained_points)):
                        for j in range(i + 1, len(contained_points)):
                            cp1 = contained_points[i]
                            cp2 = contained_points[j]

                            p1 = psl[cp1[0], cp1[1]]
                            p2 = psl[cp2[0], cp2[1]]
                            if abs(cp1[0] - cp2[0]) > 2 or abs(cp1[0] - cp2[0]) > 2:
                                is_found = False

                            #if p1 != p2:
                                #is_found = False
                                #break

                    if is_found:
                        cyclones[contained_points[0]].isobars.append(isobar)


        all_cyclones = []
        candidate_cyclones = []
        plt.ion()
        plt.cla()

        for cyclone in cyclones.values():
            all_cyclones.append(cyclone)

            if len(cyclone.isobars) == 0:
                continue
            elif cyclone.isobars[-1].pressure - cyclone.isobars[0].pressure < 500:
                continue
            else:
                area = 0
                #import ipdb; ipdb.set_trace()
                bounds_path = cyclone.isobars[-1].path
                for i in range(len(bounds_path) - 1):
                    area += bounds_path[i, 0] * bounds_path[(i + 1), 1]
                area += bounds_path[-1, 0] * bounds_path[0, 1]
                area /= 2
                #print(area)
                plt.cla()
                #plot_cyclone(cyclone)
                #raw_input()

                if run_count != 0:
                    for prev_cyclone in daily_candidate_cyclones[run_count - 1]:
                        if dist((cyclone.cell_pos.x, cyclone.cell_pos.y), (prev_cyclone.cell_pos.x, prev_cyclone.cell_pos.y)) < 10:
                            prev_cyclone.next_cyclone = cyclone
                            cyclone.prev_cyclone = prev_cyclone
            
            candidate_cyclones.append(cyclone)
            
            roci = cyclone.isobars[-1]
            cyclone_vort = vort[int(roci.ymin):int(roci.ymax) + 1,
                                int(roci.xmin):int(roci.xmax) + 1]
            cyclone_psl = psl[int(roci.ymin):int(roci.ymax) + 1,
                              int(roci.xmin):int(roci.xmax) + 1]

            cyclone_mask = cyclone_psl > roci.pressure
            cyclone.vort = np.ma.array(cyclone_vort, mask=cyclone_mask)
            cyclone.psl = np.ma.array(cyclone_psl, mask=cyclone_mask)

        run_count += 1
        daily_candidate_cyclones.append(candidate_cyclones)
        daily_all_cyclones.append(all_cyclones)

        daily_psls.append(psl)
        #daily_uws.append(u)
        #daily_vws.append(v)



    if False:
        plt.ion()
        plt.clf()

        plot_all(daily_isobars, daily_cyclone_mins, daily_psls, daily_uws, daily_vws, args)

    return daily_candidate_cyclones, np.array(times)

def plot_wilma_track():
    args = create_args()
    args.start = 1152
    args.end = 1200
    cs, pt = main(args)
    w = cs[10][10]
    plot_cyclone_track(w)

def plot_cyclone_vort(cyclone):
    plt.imshow(cyclone.vort, interpolation='nearest')

def plot_cyclone_psl(cyclone):
    plt.imshow(cyclone.psl, interpolation='nearest')

def plot_cyclone_chain(cyclone):
    plot_cyclone(cyclone)
    count = 0
    while cyclone.next_cyclone:
        count += 1
        print count

        cyclone = cyclone.next_cyclone
        plot_cyclone(cyclone)

def plot_all_tracks(all_cyclones):
    plt.figure(1)
    plt.cla()
    for cyclones in all_cyclones:
        for cyclone in cyclones:
            if cyclone.is_head:
                plot_cyclone_track(cyclone)

def plot_cyclone_track(cyclone, min_length=5):
    if cyclone.chain_length() < min_length:
        return

    coords = []
    coords.append((cyclone.cell_pos.x, cyclone.cell_pos.y))
    while cyclone.next_cyclone:
        cyclone = cyclone.next_cyclone
        coords.append((cyclone.cell_pos.x, cyclone.cell_pos.y))
    coords = np.array(coords)
    plt.plot(coords[0::4, 0], coords[0::4, 1], 'ko')
    plt.plot(coords[:, 0], coords[:, 1], 'g-')

def plot_all_cyclones(cyclones):
    plt.figure(1)
    plt.cla()
    for cyclone in cyclones:
        plot_cyclone(cyclone)

def plot_cyclone(cyclone):
    plt.plot(cyclone.cell_pos.x, cyclone.cell_pos.y, 'k+')
    for isobar in cyclone.isobars:
        #plt.xlim((0, 360))
        #plt.ylim((-90, 90))
        plt.plot(isobar.glob_path[:, 0], isobar.glob_path[:, 1])

def plot_all(daily_isobars, daily_cyclone_mins, daily_psls,  daily_uws, daily_vws,args):
    s = float(args.sleep)
    plt.figure(1)
    plt.figure(2)
    plt.figure(3)
    r = ''
    i = 0
    while r != 'q':
        if r != 'c':
            r = raw_input()
            if r == 'n':
                i += 1
            elif r == 'p':
                i -= 1
            elif r[0] == 'g':
                i = int(r[1:])
        else:
            i += 1
            if i == len(daily_isobars):
                i = 0
                r = ''
                continue

        plt.pause(s)
        if args.plot_pressures:
            plt.figure(2)
            plt.cla()
            plt.title(i + 1)
            plt.imshow(daily_psls[i][::-1], interpolation='nearest')

        if args.plot_winds:
            plt.figure(3)
            plt.cla()
            plt.title(i + 1)
            plt.quiver(daily_uws[i], daily_vws[i])

        plt.figure(1)
        plt.cla()
        plt.title(i + 1)
        for j in range(len(daily_isobars[i])):
            isobar = daily_isobars[i][j]
            contained_mp = daily_cyclone_mins[i][j][0]
            plt.plot(isobar.path[:, 0], isobar.path[:, 1])

            #plt.plot(contained_mp[1], contained_mp[0], 'kx')


def get_contour_verts(cn):
    contours = []
    # for each contour line
    for cc in cn.collections:
        paths = []
        # for each separate section of the contour line
        for pp in cc.get_paths():
            xy = []
            # for each segment of that section
            for vv in pp.iter_segments():
                xy.append(vv[0])
            paths.append(np.vstack(xy))
        contours.append(paths)

    return contours

def vorticity(u, v):
    vort = np.zeros_like(u)
    for i in range(1, u.shape[0] - 1):
        for j in range(1, u.shape[1] - 1):
            du_dy = (u[i + 1, j] - u[i - 1, j])/ 2.
            dv_dx = (v[i, j + 1] - v[i, j - 1])/ 2.
            vort[i, j] = du_dy - dv_dx
    return vort






def find_extrema(array):
    extrema = np.zeros_like(array)
    maximums = []
    minimums = []
    for i in range(1, array.shape[0] - 1):
        for j in range(0, array.shape[1]):
            val = array[i, j]

            is_max, is_min = True, True
            for ii in range(i - 1, i + 2):
                for jj in range(j - 1, j + 2):
                    if val < array[ii, jj % array.shape[1]]: 
                        is_max = False
                    elif val > array[ii, jj % array.shape[1]]: 
                        is_min = False
            if is_max:
                extrema[i, j] = 1
                maximums.append((i, j))
            elif is_min:
                extrema[i, j] = -1
                minimums.append((i, j))
    return extrema, maximums, minimums

def dist(p1, p2):
    return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5

def voronoi(extrema, maximums, minimums):
    voronoi = np.zeros_like(extrema)
    for i in range(1, voronoi.shape[0] - 1):
        for j in range(0, voronoi.shape[1]):
            min_dist = 1e9
            for k, extrema_point in enumerate(minimums + maximums):
                test_dist = dist((i, j), extrema_point)
                if test_dist < min_dist:
                    min_dist = test_dist
                    voronoi[i, j] = k

    for k, extrema_point in enumerate(minimums + maximums):
        voronoi[extrema_point[0], extrema_point[1]] = 0
    voronoi[voronoi > len(minimums)] = -1
    return voronoi


def create_args():
    parser = ArgumentParser()
    parser.add_argument('-l', '--sleep', help='Sleep time', default='0.1')
    parser.add_argument('-s', '--start', help='Number of timesteps', default='0')
    parser.add_argument('-e', '--end', help='Number of timesteps', default='10')
    parser.add_argument('-p', '--plot-pressures', help='Plot pressures', action='store_true')
    parser.add_argument('-w', '--plot-winds', help='Plot winds', action='store_true')
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = create_args()
    main(args)