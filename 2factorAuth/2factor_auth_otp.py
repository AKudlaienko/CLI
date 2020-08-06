#!/usr/bin/env python3

"""
Another one OTP generator.
A simple python script to generate One Time Password (OTP) for 2 factor authentication.
It was written an tested with GoogleAuth, but also may work with an OktaVerify QR.
To make it work you should provide either you QR code image for the GoogleAuth or the raw SECRET.


Required modules:
 - pillow
 - pyzbar
 - pyotp
"""

import sys
import time
from PIL import Image
from pyzbar.pyzbar import decode
import pyotp
import argparse

argv_parser = argparse.ArgumentParser()
argv_parser.add_argument("-r", "--refresh", help="Continuously refresh and print OTP")
group = argv_parser.add_mutually_exclusive_group(required=True)
group.add_argument("-s", "--secret", help="A secret pulled from the QR code for GoogleAuth")
group.add_argument("-qr", "--qrcode", help="A path to the QR code picture")
args = argv_parser.parse_args()


def renew_otp(secret, otp_exp_time=26):
    tmp_otp = generate_otp(secret)
    start_timestamp = int(time.time())
    while True:
        if (int(time.time()) - start_timestamp > int(otp_exp_time)):
            tmp_otp = generate_otp(secret)
        sys.stdout.flush()
        sys.stdout.write('\r Your OTP: ' + str(tmp_otp))
        time.sleep(int(otp_exp_time))


def decode_qr(qr_image):
    raw_data = decode(Image.open(qr_image))
    qr_secret = str(raw_data[0].data.decode('utf-8')).split('secret=')[1]
    if '&' in qr_secret:
        qr_secret = qr_secret.split('&')[0]
    return qr_secret


def generate_otp(secret):
    if len(secret) > 1:
        totp = pyotp.TOTP(secret)
        one_time_passwd = totp.now()
        return one_time_passwd
    else:
        print("\n* Secret key is missing!\nRead more: https://pyotp.readthedocs.io/en/latest/")
        sys.exit(1)


if __name__ == "__main__":
    if args.refresh:
        if args.secret:
            renew_otp(args.secret)
        else:
            renew_otp(decode_qr(args.qrcode))
    else:
        if args.qrcode:
            print(generate_otp(decode_qr(args.qrcode)))
        else:
            print(generate_otp(args.secret))

