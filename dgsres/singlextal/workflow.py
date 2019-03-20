"""
see
* https://jupyter.sns.gov/user/{USER}/notebooks/data/SNS/SEQ/IPTS-16800/shared/resolution/resolution%20simulations%20-%20improve%20workflow.ipynb
* https://jupyter.sns.gov/user/lj7/notebooks/data/SNS/SEQ/IPTS-16800/shared/resolution/resolution%20fit%20-%20improve%20workflow.ipynb
"""

import os, shutil, subprocess as sp, time
import numpy as np
from matplotlib import pyplot as plt
from . import use_res_comps, fit_ellipsoid, _workflow_pdf_helpers as _wph
from mcvine.workflow import singlextal as sx


def simulate_all_in_one(config):
    "simulate all grid points, and compose PDF reports"
    import pylatex
    Ei = config.Ei
    Erange = (-0.3*Ei, .95*Ei)
    for sl in config.slices:
        doc = _wph.initReportDoc("%s-sim-report" % sl.name) # report document
        # info
        _wph.slice_info_section(sl, doc)
        
        qaxis = sl.grid.qaxis; Eaxis = sl.grid.Eaxis

        # dyn range plot
        # larger q range for a broader view 
        ratio = 1.
        expanded_qaxis = sx.axis(
            min=qaxis.min-(qaxis.max-qaxis.min)*ratio/2,
            max=qaxis.max+(qaxis.max-qaxis.min)*ratio/2,
            step=qaxis.step
        ).ticks()
        width = r'1\textwidth'
        with doc.create(pylatex.Section('Dynamical range')):
            with doc.create(pylatex.Figure(position='htbp')) as plot:
                plt.figure()
                plotDynRange(
                    sl.hkl0, sl.hkl_projection,
                    qaxis= expanded_qaxis, Erange=Erange,
                    config=config)
                plot.add_plot(width=pylatex.NoEscape(width))
                plot.add_caption('Dynamical range for slice %s' % sl.name)
                plt.close()

        # simulate
        with doc.create(pylatex.Section('Simulated resolution functions on a grid')):
            outputs, failed = simulate_all_grid_points(
                slice=sl, config=config, Nrounds_beam=config.sim_Nrounds_beam, overwrite=False)

            if failed:
                # this seems unecessary as what is missing is clear in the plot
                """
                doc.append("Failed to calculate resolution functions for the following (Q,E) pairs:")
                with doc.create(pylatex.Itemize()) as itemize:
                    for f in failed:
                        itemize.add_item(str(f))
                """
                pass
            # plot
            with doc.create(pylatex.Figure(position='htbp')) as plot:
                plt.figure()
                plot_resolution_on_grid(config.GammaA, config, figsize=(10, 10))
                plot.add_plot(width=pylatex.NoEscape(width))
                plot.add_caption('Simulated resolution functions for %s' % sl.name)
                plt.close()
        # save pdf
        doc.generate_pdf(clean_tex=False)
        continue
    return

def fit_all_in_one(config):
    "fit all grid points, and compose PDF reports"
    import pylatex, dill
    Ei = config.Ei
    Erange = (-0.3*Ei, .95*Ei)
    width = r'1\textwidth'
    for sl in config.slices:
        doc = _wph.initReportDoc("%s-fit-report" % sl.name) # report document
        qaxis = sl.grid.qaxis; Eaxis = sl.grid.Eaxis
        # info
        _wph.slice_info_section(sl, doc)
        
        # fit
        with doc.create(pylatex.Section('Fit resolution functions on grid')):
            # path to saved result
            path = '%s-fit_all_grid_points.dill' % sl.name
            if os.path.exists(path):
                qE2fitter, nofit = dill.load(open(path))
            else:
                qE2fitter, nofit = fit_all_grid_points(sl, config, use_cache=True)
                dill.dump((qE2fitter, nofit), open(path, 'w'), recurse=True)
            # plot
            with doc.create(pylatex.Figure(position='htbp')) as plot:
                plt.figure()
                plot_resfits_on_grid(qE2fitter, sl, config, figsize=(10,10))
                plot.add_plot(width=pylatex.NoEscape(width))
                plot.add_caption('Fitted resolution functions for %s' % sl.name)
                plt.close()
            doc.append(pylatex.utils.NoEscape(r"\clearpage"))
        # save
        pklfile = '%s-fit_results.pkl' % sl.name
        save_fits_as_pickle(qE2fitter, pklfile)
        import pickle as pkl
        qE2fitres = pkl.load(open(pklfile))
        
        # parameters
        with doc.create(pylatex.Subsection('Fitted parameters')):
            s = format_parameter_table(qE2fitres)
            doc.append(_wph.verbatim(s))
            
        # one by one comparison plots
        with doc.create(pylatex.Section('Comparing fits to mcvine simulations')):
            for qE, fitter in qE2fitter.items():
                with doc.create(pylatex.Figure(position='htbp')) as plot:
                    plt.figure()
                    plot_compare_fit_to_data(fitter)
                    plot.add_plot(width=pylatex.NoEscape(width))
                    plot.add_caption('Resolution at q=%s, E=%s' % qE)
                    plt.close()
                doc.append(pylatex.utils.NoEscape(r"\clearpage")) # otherwise latex complain about "too many floats"
        # save PDF
        doc.generate_pdf(clean_tex=False)
        continue
    return

def plotDynRange(hkl0, hkl_projection, qaxis, Erange, config):
    from mcvine.workflow.singlextal import dynrange
    from mcvine.workflow.sample import loadSampleYml

    sample = loadSampleYml(config.sample_yaml)
    psi_scan = config.psi_scan
    psilist = np.arange(psi_scan.min, psi_scan.max, psi_scan.step)

    dynrange.plotDynRangeOfSlice(
        sample, psi_scan.ticks(), config.Ei, hkl0, hkl_projection, qaxis,
        config.instrument.scattering_angle_constraints,
        Erange=Erange)
    return 


def simulate(q, E, slice, outdir, config, Nrounds_beam=1):
    hkl0 = slice.hkl0
    hkl_projection = slice.hkl_projection
    hkl = hkl0 + hkl_projection*q
    # setup
    use_res_comps.setup(
        outdir,
        config.sample_yaml, config.beam, E, hkl, hkl_projection,
        config.psi_scan, config.instrument.instrument, config.instrument.pixel)

    # more configuration
    open(os.path.join(outdir, 'mc_params.yml'), 'wt').write("Nrounds_beam: %s"%Nrounds_beam)

    # run
    cmd = "python run.py"
    start = time.time()
    out = sp.check_output(cmd, shell=True, cwd=outdir)
    end = time.time()
    duration = end - start
    print "* simulation took %s seconds" % duration
    return out


def simulate_all_grid_points(slice, config, Nrounds_beam=1, overwrite=False):
    failed = []; outputs = {}
    for q in slice.grid.qaxis.ticks():
        for E in slice.grid.Eaxis.ticks():
            simdir = config.simdir(q,E, slice)
            if not overwrite and os.path.exists(simdir): continue
            try:
                outputs[(q,E)] = simulate(q=q, E=E, slice=slice, outdir=simdir, config=config, Nrounds_beam=Nrounds_beam)
            except:
                failed.append( (q,E) )
        continue
    return outputs, failed


def plot_resolution_on_grid(slice, config, figsize=(10, 7)):
    qs = slice.grid.qaxis.ticks()
    Es = slice.grid.Eaxis.ticks()
    ncols = len(qs)
    nrows = len(Es)
    res_2d_grid = slice.res_2d_grid
    hkl_projection = slice.hkl_projection
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    for irow in range(nrows):
        for icol in range(ncols):
            q = qs[icol]
            E = Es[irow]
            simdir = config.simdir(q,E, slice)
            try:
                probs = np.load('%s/probs.npy' % simdir)
            except IOError:
                continue
            dEs = np.load('%s/dEs.npy' % simdir)
            dhkls = np.load('%s/dhkls.npy' % simdir)
            dqs = np.dot(dhkls, hkl_projection)/np.linalg.norm(hkl_projection)**2
            I, dqedges, dEedges = np.histogram2d(
                bins=(res_2d_grid.qaxis.ticks(), res_2d_grid.Eaxis.ticks()), weights=probs, x=dqs, y=dEs )
            dqg, dEg = np.meshgrid(dqedges, dEedges)
            ax1 = axes[irow][icol]
            median = np.nanmedian(I[I>0])
            good = I[I<median*200]
            goodmax = good.max()
            I[I>median*100] = goodmax
            ax1.set_title("q=%.2f, E=%.2f" % (q, E))
            ax1.pcolormesh(dqg, dEg, I.T)
    plt.tight_layout()
    return


def fit(q, E, slice, config, use_cache=False):
    if use_cache:
        import dill
        path = '%s-q_%.3f-E_%.3f-fitter.dill' % (slice.name, q, E)
        if os.path.exists(path):
            return dill.load(open(path))
    from dgsres.singlextal import fit_ellipsoid
    datadir = config.simdir(q,E,slice)
    qaxis = slice.res_2d_grid.qaxis
    Eaxis = slice.res_2d_grid.Eaxis
    fitter = fit_ellipsoid.Fit(
        datadir,
        qaxis=(qaxis.min, qaxis.max, qaxis.step),
        Eaxis=(Eaxis.min, Eaxis.max, Eaxis.step),
        Ei=config.Ei, E=E
    )
    fitter.load_mcvine_psf_qE(adjust_energy_center=True)
    fitting_params = dict([(k,v) for k,v in slice.fitting.__dict__.items() if not k.startswith('_')])
    fitter.fit_result = fitter.fit(**fitting_params)
    if use_cache:
        dill.dump(fitter, open(path, 'w'))
    return fitter


def plot_compare_fit_to_data(fitter, figsize=(8,8)):
    res_z = fitter.res_z
    qgrid, Egrid = fitter.qEgrids
    result = fitter.fit_result
    plt.figure(figsize=figsize)
    plt.subplot(2,2,1)
    plt.title('mcvine sim')
    plt.pcolormesh(qgrid, Egrid, res_z)
    plt.colorbar()
    plt.subplot(2,2,2)
    plt.title('fit')
    scale = res_z.sum()/result.best_fit.sum()
    iqe_fit = result.best_fit.reshape(res_z.shape)*scale
    plt.pcolormesh(qgrid, Egrid, iqe_fit)
    plt.colorbar()

    qs = qgrid[0]; Es = Egrid[:,0]
    plt.subplot(2,2,3)
    plt.plot(qs, res_z.sum(0), label='mcvine sim')
    plt.plot(qs, iqe_fit.sum(0), label='fit')
    plt.legend()
    plt.subplot(2,2,4)
    plt.plot(Es, res_z.sum(1), label='mcvine sim')
    plt.plot(Es, iqe_fit.sum(1), label='fit')
    plt.legend()
    
    return

def fit_all_grid_points(slice, config, use_cache=False):
    qE2fitter = dict()
    nofit = []
    for q in slice.grid.qaxis.ticks():
        for E in slice.grid.Eaxis.ticks():
            print q, E
            try:
                qE2fitter[(q,E)] = fit(q, E, slice, config, use_cache=use_cache)
            except:
                nofit.append((q,E))
        continue
    # qEranges is an import parameter that need to be rememberd
    fitter1 = qE2fitter.values()[0]
    slice.res_2d_grid.qEranges = fit_ellipsoid.qEgrid2range(*fitter1.qEgrids)
    for fitter in qE2fitter.values()[1:]:
        assert slice.res_2d_grid.qEranges == fit_ellipsoid.qEgrid2range(*fitter.qEgrids)
    return qE2fitter, nofit

def plot_resfits_on_grid(qE2fitter, slice, config, figsize=(10, 7)):
    qs = slice.grid.qaxis.ticks()
    Es = slice.grid.Eaxis.ticks()
    ncols = len(qs)
    nrows = len(Es)
    res_2d_grid = slice.res_2d_grid
    hkl_projection = slice.hkl_projection
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    for irow in range(nrows):
        for icol in range(ncols):
            q = qs[icol]
            E = Es[irow]
            fitter = qE2fitter.get((q,E))
            if fitter is None: continue
            dqgrid, dEgrid = fitter.qEgrids
            result = fitter.fit_result
            ax1 = axes[irow][icol]
            ax1.set_title("q=%.2f, E=%.2f" % (q, E))
            ax1.pcolormesh(dqgrid, dEgrid, result.best_fit.reshape(dqgrid.shape))
    plt.tight_layout()
    return

def save_fits_as_pickle(qE2fitter, path):
    qE2fitres_tosave = dict()

    for qe in qE2fitter.keys():
        fr = qE2fitter[qe].fit_result
        fr_tosave = fit_ellipsoid.FitResult()
        fr_tosave.best_values = fr.best_values
        qE2fitres_tosave[qe] = fr_tosave
        continue

    import pickle as pkl
    pkl.dump(qE2fitres_tosave, open(path, 'w'))
    return

def format_parameter_table(qE2fitres):
    keys = qE2fitres.values()[0].best_values.keys()
    lines = []
    line = "%6s%6s" % ('q','E')
    for k in keys: line += '%8s' % k[:8]
    lines.append(line)
    qEs = qE2fitres.keys()
    for q, E in qEs:
        if not (q,E) in qE2fitres: continue
        result = qE2fitres[(q,E)]
        line = "%6.1f%6.1f" % (q,E)
        for k in keys:
            v = result.best_values[k]
            line += '%8.4f' % v
        lines.append(line)
    return '\n'.join(lines)

def print_parameter_table(qE2fitres):
    s = format_parameter_table(qE2fitres)
    return s

def create_interp_model(qE2fitres, slice):
    # Get parameters as lists, ready for interpolation
    keys = qE2fitres.values()[0].best_values.keys()
    qEs_all = qE2fitres.keys()
    qE_points = []
    param_values = dict()
    for k in keys:
        param_values[k] = []
    for q,E in qEs_all:
        if (q,E) not in qE2fitres: continue
        result = qE2fitres[(q,E)]
        bv = result.best_values
        qE_points.append((q,E))
        for k in keys:
            vals = param_values[k]
            v = bv[k]
            vals.append(v)
        continue
    qrange, Erange = slice.res_2d_grid.qEranges
    return fit_ellipsoid.InterpModel(qE_points, param_values, qrange, Erange)
