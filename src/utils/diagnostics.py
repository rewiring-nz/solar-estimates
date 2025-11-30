import xarray as xr


def print_wrf_diagnostics(nc_file_path):
    """Load a WRF NetCDF file and print comprehensive diagnostic information."""

    print("=" * 80)
    print("WRF NetCDF FILE DIAGNOSTICS")
    print("=" * 80)
    print(f"\nFile: {nc_file_path}\n")

    ds = xr.open_dataset(nc_file_path, engine="h5netcdf")

    print("-" * 80)
    print("DATASET OVERVIEW")
    print("-" * 80)
    print(ds)
    print()

    print("-" * 80)
    print("DATASET INFO")
    print("-" * 80)
    print(ds.info())
    print()

    print("-" * 80)
    print("DIMENSIONS")
    print("-" * 80)
    for dim_name, dim_size in ds.sizes.items():
        print(f"  {dim_name}: {dim_size}")
    print()

    print("-" * 80)
    print("COORDINATES")
    print("-" * 80)
    for coord_name, coord_data in ds.coords.items():
        print(f"\n  {coord_name}:")
        print(f"    Shape: {coord_data.shape}")
        print(f"    Dtype: {coord_data.dtype}")
        print(f"    Min: {coord_data.min().values}, Max: {coord_data.max().values}")
        if coord_data.attrs:
            print(f"    Attributes: {dict(coord_data.attrs)}")
    print()

    print("-" * 80)
    print("DATA VARIABLES")
    print("-" * 80)
    for var_name, var_data in ds.data_vars.items():
        print(f"\n  {var_name}:")
        print(f"    Shape: {var_data.shape}")
        print(f"    Dtype: {var_data.dtype}")
        print(f"    Dimensions: {var_data.dims}")
        try:
            print(f"    Min: {var_data.min().values}, Max: {var_data.max().values}")
            print(f"    Mean: {var_data.mean().values}")
        except Exception as e:
            print(f"    (Could not compute statistics: {e})")
        if var_data.attrs:
            print("    Attributes:")
            for attr_key, attr_val in var_data.attrs.items():
                print(f"      {attr_key}: {attr_val}")
    print()

    print("-" * 80)
    print("GLOBAL ATTRIBUTES")
    print("-" * 80)
    if ds.attrs:
        for attr_key, attr_val in ds.attrs.items():
            print(f"  {attr_key}: {attr_val}")
    else:
        print("  No global attributes found")
    print()

    print("-" * 80)
    print("COORDINATE REFERENCE SYSTEM INFO")
    print("-" * 80)
    try:
        if hasattr(ds, "rio"):
            print(f"  CRS: {ds.rio.crs}")
            print(f"  Transform: {ds.rio.transform()}")
            print(f"  Bounds: {ds.rio.bounds()}")
        else:
            print("  No rioxarray spatial metadata found")
    except Exception as e:
        print(f"  Could not retrieve CRS info: {e}")
    print()

    print("=" * 80)
    print("END OF DIAGNOSTICS")
    print("=" * 80)
    print()

    return ds
