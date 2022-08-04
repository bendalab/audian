import audian

filepath = 'feldgr.wav'

high_pass = 500.0

audian.main(['-f', f'{high_pass}', filepath])
