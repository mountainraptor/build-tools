#!/usr/bin/python
# This python script decrypts data (*.mod) to a plaintext file.  The .enc file
# is an encrypted file that has been encrypted with a public key and signed with
# a private key
#
# The .enc file has the following format:
# +------------------------+
# +       signature        +
# +      [512 bytes]       +
# +------------------------+
# + RSA encrypted password +
# +      [512 bytes]       +
# +------------------------+
# +   RSA encrypted salt   +
# +      [512 bytes]       +
# +------------------------+
# + RSA encrypted filename +
# +      [512 bytes]       +
# +------------------------+
# +      Symmetric Key     +
# +    encrypted package   +
# +      [file.pack]     +
# +------------------------+

import sys, re, argparse, os, subprocess, shutil, struct, binascii, tempfile
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
import json


def build_header(romgHeaderFile, encryptionKey, signingKey):
    header = None
    with open(romgHeaderFile, 'r') as f:
        header = json.loads(f.read())
    if header:
        #find the decrytion key hash that will be used to decryt this module
        header['encryptionKeyHash'] = get_complementary_key_sha256_hash(encryptionKey)
        #find the decrytion key hash that will be used to decryt this module
        header['signatureKeyHash'] = get_complementary_key_sha256_hash(signingKey)
        return header

def get_sha256(in_filename):
    CHUNK_SIZE = 16*1024
    file_sha256_checksum = SHA256.new()
    with open(in_filename, 'rb') as infile:
        while True:
            chunk = infile.read(CHUNK_SIZE)
            if len(chunk) == 0:
                break
            file_sha256_checksum.update(chunk)
        infile.close()
    return file_sha256_checksum

def get_complementary_key_sha256_hash(keyFile):
    """
    Given a key it will look in the same directory and find the complementary key and return the sha256 hash of that key
    The complementary key is the pulbic key if keyFile is a private key or a private key if keyFile is a public key.
    """
    keyDir = os.path.dirname(keyFile)
    keyFiles = [os.path.join(keyDir, f) for f in os.listdir(keyDir) if os.path.isfile(os.path.join(keyDir, f))]
    rsaKeyInfo = None
    with open(keyFile, 'r') as f:
        rsaKeyInfo = RSA.importKey(f.read())
    if not rsaKeyInfo:
        raise Exception("Could not read in rsa key %s" % (keyFile))
    for kf in keyFiles:
        try:
            f = open(kf, 'r')
            rsakey = RSA.importKey(f.read())
            f.close()
            sha256 = get_sha256(kf)
            if rsaKeyInfo.has_private() and not rsakey.has_private() and rsaKeyInfo.publickey() == rsakey.publickey():
                return sha256.hexdigest()
            elif not rsaKeyInfo.has_private() and rsakey.has_private() and rsaKeyInfo.publickey() == rsakey.publickey():
                return sha256.hexdigest()
        except Exception:
            pass
    return None


def __make_parser():
    p = argparse.ArgumentParser(description='This decrypts an encrypted file')
    p.add_argument('-r', '--romg-file', type=str, help='the romg file to generate an omg for', default=None, required = True)
    p.add_argument('-H', '--romg-header', type=str, help='do not include the filename in the package', default = False, required = True)
    p.add_argument('-e', '--encryption-key', type=str, help='the private key used to encrypt the file', default=None, required = True)
    p.add_argument('-s', '--signing-key', type=str, help='the public key used to verify the signature', default=None, required = True)
    p.add_argument('-v', '--verbose', action='store_true', help='verbose message printing', default = False, required = False)
    p.add_argument('-d', '--output-directory', type=str, help='specify an alternate output directory for the decrypted file', default = None, required = False)
    return p

def __main(argv):
    parser = __make_parser()
    settings = parser.parse_args(argv[1:])
    MYDIR = os.path.dirname(os.path.realpath(__file__))

    if (not os.path.isfile(settings.romg_file)):
        sys.stderr.write('Error romg file is not a valid file\n')
        sys.exit(1)
    if (not os.path.isfile(settings.romg_header)):
        sys.stderr.write('Error romg file is not a valid file\n')
        sys.exit(1)
    if (not os.path.isfile(settings.encryption_key)):
        sys.stderr.write('Error encryption key file is not a valid file\n')
        sys.exit(1)
    if (not os.path.isfile(settings.signing_key)):
        sys.stderr.write('Error signing_key file file is not a valid file\n')
        sys.exit(1)

    settings.romg_header = os.path.abspath(settings.romg_header)
    settings.romg_file = os.path.abspath(settings.romg_file)
    settings.encryption_key = os.path.abspath(settings.encryption_key)
    settings.signing_key = os.path.abspath(settings.signing_key)

    header = build_header(settings.romg_header, settings.encryption_key, settings.signing_key)
    headerStr = json.dumps(header)
    headerStr = '%d#' % (len(headerStr)) + headerStr
    notUsed, tmpfname = tempfile.mkstemp(prefix='omg-header')
    with open(tmpfname, 'w') as fh:
        fh.write(headerStr)

    encryptScript = os.path.abspath(os.path.join(MYDIR, 'encrypt-data.py'))
    args = [encryptScript, '-e', settings.encryption_key, '-s', settings.signing_key, '-t', settings.romg_file, '-H', tmpfname]
    if settings.output_directory:
        args.append('-d')
        args.append(settings.output_directory)
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutstr, stederrstr = p.communicate()
    p.wait()
    os.remove(tmpfname)
    if p.returncode == 0 and stdoutstr != None:
        encFname = stdoutstr.replace('\n', '')
        omgFileName = encFname.replace('.enc', '.omg')
        os.rename(encFname, omgFileName)
        print omgFileName

    sys.exit(p.returncode)

if __name__ == "__main__":
    __main(sys.argv)

__doc__ += __make_parser().format_help()
