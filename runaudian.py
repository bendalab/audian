import audian    # install via pip: pip install audian

filepath = 'feldgr.wav'
audian.main(['-f', '1000', '-l', '15000', filepath])

# in Spyder ipython console do
# %set_env MPLBACKEND=
# then you can do
# ! audian -f 1000 -l 15000 data.wav

