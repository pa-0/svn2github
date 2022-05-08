# TODO

```
WARNING this is just a draft
i currently dont need this tool any longer
so i have no time to finish it

but it should work ...
you only need to
1. set github_username
2. set github_token
3. create empty folder with two files
3a. svn2github.json
3b. your-repo-name.rules
4. either/or:
4a. chdir to your folder, and run "svn2github.py update"
4b. run "svn2github.py -C path/to/folder/ update"

features:
* fast convert with svn-all-fast-export
  this probably works only for the first conversion
  and not for incremental updates
  as it creates an empty git repo on every run (?)

todo implement
* automatic upload to sourceforge.net
  * dump the svnrepo (not needed if you used svnrdump, not svnsync, to fetch the orignal repo)
    * svnadmin info svnrepo/ | grep Revisions
    * svnadmin dump --quiet --incremental --revision 0000:0999 --file svn-dump.0 svnrepo/
    * svnadmin dump --quiet --incremental --revision 1000:1999 --file svn-dump.1 svnrepo/
    * svnadmin dump --quiet --incremental --revision 2000:2999 --file svn-dump.2 svnrepo/
    * ...
  * upload the svn-dump.* files to sf.net

TODO store the original svn repo on sourceforge.net
sf.net allows download with rsync, which is much faster than svnsync
(maybe also faster than svnrdump dump)
```

## useful svn commands

```sh
# get info from remote
svn info svn://svn.jdownloader.org/jdownloader

# get info from local
svnadmin info jdownloader/svnrepo/

# set uuid
svnadmin setuuid jdownloader/svnrepo/ ebf7c1c2-ba36-0410-9fe8-c592906822b4
```

## upload to sourceforge.net

based on

https://sourceforge.net/p/forge/documentation/svn/#accessing-the-repository-via-the-shell

https://sourceforge.net/p/forge/documentation/SVN%20Import/

expected result:

https://sourceforge.net/p/jdownloader-svn-mirror-milahu/code/HEAD/tree/

this can be fetched with rsync

```
rsync -r rsync://svn.code.sf.net/p/jdownloader-svn-mirror-milahu/code/ ./jdownloader
```

in this example, rsync takes about 8 minutes to fetch a 2GB svnrepo

svnsync takes 6 hours (!) for the same repo
([svnsync performance drops exponentially over time](https://stackoverflow.com/a/70204019/10440128))

svnrdump should be faster than svnsync

### create sourceforge project

create a new project, for example

https://sourceforge.net/p/jdownloader-svn-mirror-milahu

### sourceforge svn version

sourceforge has svn version 1.9.5
and the supported svn filesystem version is 1.9.0

```
$ svn --version 
svn, version 1.9.5 (r1770682)
```

on my local machine (nixos linux), i have svn version 1.14.2
which creates svnrepo with filesystem version 1.10.0

```
$ svn --version 
svn, version 1.14.2 (r1899510)
```

if you upload filesystem version is 1.10.0
then sourceforge can not parse your svnrepo

```
$ svnadmin info . 
svnadmin: E160043: Expected FS format between '1' and '7'; found format '8'
```

and sourceforge can also not convert your svnrepo to the 1.9.0 format
so you must upload the 1.9.0 format

https://stackoverflow.com/questions/38101909/subversion-1-9-in-raspberry-pi-contains-invalid-filesystem-format-option-addre

```
svnadmin info svnrepo/ | grep Compat
# Compatible With Version: 1.10.0

# convert svn filesystem format
svnadmin create --compatible-version=1.9.0 svnrepo-svn-1.9.0/
svnadmin dump svnrepo/ | svnadmin load --quiet svnrepo-svn-1.9.0/

svnadmin info svnrepo-svn-1.9.5/ | grep Compat
# Compatible With Version: 1.9.0
```

i use `svnadmin load --quiet` as `svnadmin load` is too verbose

### fast: init svnrepo by file copy

replace `milahu` with your sourceforge username

replace `jdownloader-svn-mirror-milahu` with your sourceforge project-name

```
# local
  tar czf - svnrepo/ | split --verbose --bytes=100MB - svnrepo.tar.gz.
  # wait for tar to finish, then upload all files
  scp svnrepo.tar.gz.* milahu@frs.sourceforge.net:/home/project-web/jdownloader-svn-mirror-milahu/
# remote
ssh -t milahu,jdownloader-svn-mirror-milahu@shell.sourceforge.net create
  cd /home/svn/p/jdownloader-svn-mirror-milahu/code
  rm -rf * # delete old svn files
  cat /home/project-web/jdownloader-svn-mirror-milahu/svnrepo.tar.gz.* | tar xzf -
  svnadmin info . | grep UUID # should be same as the local UUID
  rm /home/project-web/jdownloader-svn-mirror-milahu/svnrepo.tar.gz.* # remove temprary files
```

### fast: init svnrepo by svn dump and load

[svnadmin load via the shell](https://sourceforge.net/p/forge/documentation/SVN%20Import/#svnadmin-load-via-the-shell)

```sh
svnadmin info jdownloader/svnrepo/
# Revisions: 45958

# local: dump svnrepo. not needed if you used svnrdump
last=45958
incr=1000
for start in $(seq 0 $incr $last); do
  end=$((start + incr - 1))
  (( end > last )) && end=$last
  o=$(printf "svndump_%010d_%010d" $start $end)
  echo "$o"
  svnadmin dump --incremental -r "$start:$end" svnrepo/ > "$o"
done

# upload files
scp svndump_* milahu@frs.sourceforge.net:/home/project-web/jdownloader-svn-mirror-milahu/

# remote
ssh -t milahu,jdownloader-svn-mirror-milahu@shell.sourceforge.net create
  for f in /home/project-web/jdownloader-svn-mirror-milahu/svndump_*; do
    svnadmin load /home/svn/p/jdownloader-svn-mirror-milahu/code < $f &&
    rm $f
  done
  timeleft # limit is 4 hours. should be enough for svnadmin load
```

### fast: svnrdump

see [svnrdump](https://sourceforge.net/p/forge/documentation/SVN%20Import/#svnrdump)

### slow: init svnrepo by svnsync

see [svnsync via local repository](https://sourceforge.net/p/forge/documentation/SVN%20Import/#svnsync-via-local-repository)

but `svnsync` is slow

## upload to github: file size limits

soft limit: 50MB per file

hard limit: 100MB per file

for example, trying to upload a large svnrepo to github will throw the error

```
$ git push github -u svnrepo 
Enumerating objects: 92042, done.
Counting objects: 100% (92042/92042), done.
Delta compression using up to 4 threads
Compressing objects: 100% (91952/91952), done.
Writing objects: 100% (92042/92042), 1.51 GiB | 1.40 MiB/s, done.
Total 92042 (delta 81), reused 92042 (delta 81), pack-reused 0
remote: Resolving deltas: 100% (81/81), done.
remote: warning: File db/revs/27/27859 is 53.09 MB; this is larger than GitHub's recommended maximum file size of 50.00 MB
remote: warning: File db/revs/39/39286 is 58.80 MB; this is larger than GitHub's recommended maximum file size of 50.00 MB
remote: warning: File db/revs/18/18251 is 52.41 MB; this is larger than GitHub's recommended maximum file size of 50.00 MB
remote: error: Trace: e1d9f53de274117bd4b8acf6737120537c438b0f5df8ea717156cf29f4fe88d2
remote: error: See http://git.io/iEPt8g for more information.
remote: error: File db/revs/39/39914 is 112.26 MB; this exceeds GitHub's file size limit of 100.00 MB
remote: error: File db/revs/41/41846 is 215.95 MB; this exceeds GitHub's file size limit of 100.00 MB
remote: error: File db/revs/26/26363 is 122.37 MB; this exceeds GitHub's file size limit of 100.00 MB
remote: error: File db/revs/26/26511 is 117.92 MB; this exceeds GitHub's file size limit of 100.00 MB
remote: error: GH001: Large files detected. You may want to try Git Large File Storage - https://git-lfs.github.com.
To https://github.com/milahu/jdownloader-svnrepo.git
 ! [remote rejected]     svnrepo -> svnrepo (pre-receive hook declined)
error: failed to push some refs to 'https://github.com/milahu/jdownloader-svnrepo.git'
```

move large files to git-lfs with

```
git lfs migrate import --above=50MiB
```

total size of all files in git lfs

```
git lfs ls-files  --debug | grep 'size:' | awk '{n+=$2} END{print n}' | numfmt --to=si
```

## upload to github: repo size limits

i got this email from github

> [GitHub] Git LFS disabled for milahu
> 
> Git LFS has been disabled on your personal account milahu because you’ve exceeded your data plan by at least 150%. Please purchase additional data packs to cover your bandwidth and storage usage:
> 
> https://github.com/account/billing/data/upgrade
> 
> Current usage as of 12 May 2022 02:50AM UTC:
> 
> Bandwidth: 0.0 GB / 1 GB (0%)
> 
> Storage: 1.6 GB / 1 GB (160%)

1.6 GB should be the bare git repo size

```
git gc
du -sh .git/
```

solutions?

* pay for github pro
* selfhost the git repo on ipfs

(personally, i gave up on mirroring the jdownloader repo, as it has low priority)
