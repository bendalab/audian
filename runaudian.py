import audian    # install via pip: pip install audian

filepath = 'feldgr.wav'
audian.main(['-f', '1000', '-l', '15000', filepath])
