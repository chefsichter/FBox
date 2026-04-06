# fbox Usage

## Starting a container

```bash
fbox                    # use current directory
fbox /path/to/project   # use specific path
fbox mycontainer        # reuse by name
fbox -p sandbox         # use named profile
```

## Container management

```bash
fbox ls                 # list all known containers
fbox inspect 2          # show container details by ID
fbox rm 2               # remove container by ID
fbox commit             # snapshot container as versioned image
```

## Profile management

```bash
fbox profiles ls        # list profiles
fbox profiles new       # create profile interactively
fbox profiles edit 1    # edit profile by ID
fbox profiles default 1 # set default profile
fbox profiles rm 1      # delete profile
fbox pf ...             # shorthand for profiles
```

## Configuration

```bash
fbox --config           # open config.toml in editor
fbox --debug            # show runtime diagnostics
```

## fbox commit workflow

1. Auto-detects container from current directory (or prompts to choose)
2. Proposes a semver-bumped image tag (patch by default)
3. Runs `docker commit` with a spinner
4. Prompts to update a profile's `default_image` in `config.toml`
