import h5py
import numpy as np
import yaml
from mcvine.workflow import singlextal as sx
import warnings
import copy


class slice(object):
    def __init__(self, name):
        self.name = name
        self.grid = grid()
        self.res_2d_grid = grid()
        self.fitting = fitting()
        self.expdata = expdata()
        self.convolution = convolution()


class grid(object):
    def __init__(self):
        self.qaxis = None
        self.Eaxis = None


class fitting(object):
    def __init__(self):
        self.rounds = 3
        self.gaussian2d_threshold = 0.5
        self. alpha_bounds = (-np.pi/2, np.pi/2)


class expdata():
    def __init__(self):
        self.grid = grid()
        self.perp_hkl_directions = None
        self.dh = None
        self.sl = None
        self.perp_hkl_range = None
        self.Nsample_perp_hkl = 20


class convolution():
    def __init__(self):
        self.expansion_ratio = 0.1
        self.N_subpixels = 5, 5


def sample_from_MDH(fl_name, yml_file=None):
    """ get the sample info from the MDH file
        fl_name is the name of the MDH file
        yml_file is an output yml file. if None no file is output.
        returns the dictionary use to send to yaml
    """

    OL = {}
    with h5py.File(fl_name, 'r') as fh:
        smpl_pth = '/MDHistoWorkspace/experiment0/sample'
        OL_pth = smpl_pth+"/oriented_lattice"
        kys = list(fh[OL_pth])
        OL['name'] = fh[smpl_pth].attrs['name'].decode()
        for ky in kys:
            if ky.find('unit_cell') >= 0:
                OL[ky.split('cell_')[1]] = fh['{}/{}'.format(OL_pth, ky)][:][0]
            if ky.find('orientation_matrix') >= 0:
                OL['UB'] = fh['{}/{}'.format(OL_pth, ky)][:]
    yml_dict = prep_for_yml(OL)
    if yml_file is not None:
        with open(yml_file, 'w') as fh:
            fh.write(yaml.dump(yml_dict))
    return yml_dict


def angles_from_MDH(fl_name):
    """get the angle info from each experiment in an MDH"""
    with h5py.File(fl_name, 'r') as fh:
        jq = list(fh["/MDHistoWorkspace"].keys())
        explist = [i for i in jq if i.find('experiment') >= 0]
        angles = np.zeros(len(explist))
        for idx, exp in enumerate(explist):
            angles[idx] = fh["/MDHistoWorkspace/{}/logs/omega/value".format(exp)][:].mean()
    angles = np.sort(angles)
    dangles = angles[1:]-angles[:-1]
    if len(np.unique(dangles)) > 1:
        warnings.warn("Warning the angles are not equally spaced")
    return sx.axis(min=angles[0], max=angles[-1], step=dangles[0])


def det_E_dir(fdh):
    """
       for a file object from an MDH file dermine which of the data
       items is the energy axis
    """
    E_ky = None
    try:
        dkeysstr = fdh['MDHistoWorkspace/data/signal'].attrs['axes'].decode('utf')
    except AttributeError:
        dkeysstr = fdh['MDHistoWorkspace/data/signal'].attrs['axes']
    dkeys = dkeysstr.split(':')
    for ky in dkeys:
        lngnm = fdh['MDHistoWorkspace/data'][ky].attrs['long_name']
        # decode from binary string  if it is one
        try:
            lngnm = lngnm.decode('utf-8')
        except AttributeError:
            pass
        if 'DeltaE' in lngnm:
            E_ky = ky
    return dkeys, E_ky


def slice_from_MDH(fl_name, slice_name, load_signal=False):
    """ get the slice info from an MDH"""
    sl = slice(slice_name)
    with h5py.File(fl_name, 'r') as fh:
        projection = fh['MDHistoWorkspace/experiment0/logs/W_MATRIX/value'][:]
        projection = projection.reshape((3, 3))  # need to check that this reshapes the matrix correctly.
        # data_shp = np.array(fh['MDHistoWorkspace/data/signal'].shape)[::-1]  # the shape of the data the first dimension is the last item in the tuple thus why reversing the array
        data_shp = np.array(fh['MDHistoWorkspace/data/signal'].shape)
        singledims = data_shp == 1
        Dky_lst, E_axis = det_E_dir(fh)
        E_axis_idx = Dky_lst.index(E_axis)
        dim_idx_list = [0, 1, 2, 3]
        all_Qdims = copy.deepcopy(dim_idx_list)
        all_Qdims.remove(E_axis_idx)
        print("Eaxis_idx ={}, All_Qdims={}, data_shp = {}".format(E_axis_idx, all_Qdims,data_shp))

        if singledims.sum() < 2:
            raise RuntimeError('Must be a slice or a cut not a volume')

        Qdims = np.where(np.invert(singledims[all_Qdims]))[0]  # An array of booleans for which Q dimensions vary
        Q_perp_dims = np.where(singledims[all_Qdims])[0]  # An array of booleans for which Q dimensions are fixed.

        if singledims[E_axis_idx]:
            # check if constant E cut # not completed yet.
            qs = {}
            for Qdim in all_Qdims:
                qs[Qdim] = fh['MDHistoWorkspace/data/D{}'.format(Qdim)]

        else:  # it is a constant Q cut
            hkl0 = np.zeros(3)
            for dimnum in range(len(Q_perp_dims)):
                qdim = Q_perp_dims[dimnum]
                qtmp = fh['MDHistoWorkspace/data/D{}'.format(qdim)][:].mean()
                hkl0 += projection[qdim, :]*qtmp
            hkl_projection = projection[Qdims[0]]
            Etmp = fh['MDHistoWorkspace/data/{}'.format(E_axis)][:]
            Evals = (Etmp[1:]+Etmp[:-1])/2
            Eaxis = sx.axis(min=Evals.min(), max=Evals.max(),
                            step=Evals[1]-Evals[0])
            qtmp = fh['MDHistoWorkspace/data/D{}'.format(Qdims[0])]
            qvals = (qtmp[1:]+qtmp[:-1])/2
            qaxis = sx.axis(min=qvals.min(), max=qvals.max(),
                            step=qvals[1]-qvals[0])
            sl.hkl0 = hkl0
            sl.hkl_projection = hkl_projection
            sl.grid.qaxis = qaxis
            sl.grid.Eaxis = Eaxis
        if load_signal:
            sl.expdata.sl = np.array(fh['MDHistoWorkspace/data/signal'])
    return sl


def gen_lattice_vectors(a, b, c, alpha, beta, gamma):
    """a, b, c lattice parameters in Angstroms
    alpha, beta,gamma lattice angles in degrees
    returns a list of the basis vectors"""
    v1 = np.array([a, 0, 0])
    bprojx = b*np.cos(np.radians(gamma))
    bprojy = np.sqrt(b*b - bprojx*bprojx)
    v2 = np.array([bprojx, bprojy, 0])
    cprojx = c*np.cos(np.radians(beta))
    cprojy = (b*c*np.cos(np.radians(alpha))-v2[0]*cprojx)/v2[1]
    cprojz = np.sqrt(c*c - cprojx**2-cprojy**2)
    v3 = np.array([cprojx, cprojy, cprojz])
    return [v1, v2, v3]


def lst2str(lst, fmtstr='{:0.5f}'):
    """converts a list to a comma seperated string
    lst is the list to convert
     fmtstr is an optional format string to tell how to display each item """

    return ','.join([fmtstr.format(vi) for vi in lst])


def prep_for_yml(OL):
    """ transform OL dictionary for use in Yaml"""
    yml_dict = {'name': OL['name'], 'chemical_formula': OL['name']}
    latt_list = [OL['a'], OL['b'], OL['c'],
                 OL['alpha'], OL['beta'], OL['gamma']]
    latt_str = lst2str(latt_list[:3])+','
    latt_str += lst2str(latt_list[3:], fmtstr='{:0.3f}')
    yml_dict['lattice'] = {'constants': latt_str}
    latt_v = gen_lattice_vectors(*latt_list)
    yml_dict['lattice']['basis_vectors'] = [lst2str(vt) for vt in latt_v]
    yml_dict['excitations'] = [{'type': 'DGSresolution'}]
    UBi = np.linalg.inv(OL['UB'])
    u = np.dot(UBi, [0, 0, 1])
    v = np.dot(UBi, [1, 0, 0])
    ul = (u/np.abs(u).max()).tolist()
    vl = (v/np.abs(v).max()).tolist()
    yml_dict['orientation'] = {'u': lst2str(ul), 'v': lst2str(vl)}
    yml_dict['shape'] = 'cylinder radius="12.5*mm" height="10.0*mm"'
    yml_dict['temperature'] = '0.3*K'
    return yml_dict
