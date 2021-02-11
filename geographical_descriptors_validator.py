from pymarc import MARCReader
from tqdm import tqdm


def log_to_file(file, message):
    with open(file, 'a', encoding='utf-8') as f:
        f.write(message)


def check_defg_034(rec_id_001: str,
                   rec_id_009: str,
                   rcd_name: str,
                   coords) -> bool:
    is_valid = True

    list_of_coords_transformed_to_decimal = []
    errors = []

    for subfield in 'defg':
        if coords.get_subfields(subfield):

            # each subfield should appear in field only once
            if len(coords.get_subfields(subfield)) != 1:
                errors.append(f'Problem z podpolem {subfield} - '
                              f'występuje {len(coords.get_subfields(subfield))} razy.')
                is_valid = False

            # if subfield count is ok, check for other errors
            else:

                # should be dms, not decimal
                if '.' in coords.get_subfields(subfield)[0]:
                    errors.append(f'Problem z podpolem {subfield} - '
                                  f'zdaje się, że to już stopnie dziesiętne - <<{coords.get_subfields(subfield)[0]}>>.')
                    is_valid = False

                # should be in format HDDDMMSS
                if len(coords.get_subfields(subfield)[0]) != 8:
                    errors.append(f'Problem z podpolem {subfield} - '
                                  f'zła długość, powinno być 8, a jest {len(coords.get_subfields(subfield)[0])} - '
                                  f'<<{coords.get_subfields(subfield)[0]}>>.')
                    is_valid = False
                if subfield in ['d', 'e'] and coords.get_subfields(subfield)[0][0] not in ['E', 'W']:
                    errors.append(f'Problem z podpolem {subfield} - '
                                  f'powinno zaczynać się od E lub W (długość geogr.), tymczasem: '
                                  f'<<{coords.get_subfields(subfield)[0]}>>.')
                    is_valid = False
                if subfield in ['f', 'g'] and coords.get_subfields(subfield)[0][0] not in ['N', 'S']:
                    errors.append(f'Problem z podpolem {subfield} - '
                                  f'powinno zaczynać się od N lub S (szerokość geogr.), tymczasem: '
                                  f'<<{coords.get_subfields(subfield)[0]}>>.')
                    is_valid = False

                # should contain only digits after hemisphere
                if not coords.get_subfields(subfield)[0][1:].isdigit():
                    errors.append(f'Problem z podpolem {subfield} - '
                                  f'zawiera inne znaki niż cyfry po znaku półkuli: '
                                  f'<<{coords.get_subfields(subfield)[0]}>>.')
                    is_valid = False

            # if coord seems ok, convert to decimal for further examination
            if is_valid:
                list_of_coords_transformed_to_decimal.append(dms_to_decimal(coords.get_subfields(subfield)[0]))

        else:
            errors.append(f'Problem z podpolem {subfield} - '
                          f'nie występuje.')
            is_valid = False

    # list should contain 4 coords
    if len(list_of_coords_transformed_to_decimal) == 4:
        lon_min = -180.0
        lon_max = 180.0
        lat_min = -90.0
        lat_max = 90.0

        d, e, f, g = list_of_coords_transformed_to_decimal

        # check min and max values
        if not lon_min <= d <= lon_max:
            errors.append(f'Problem z podpolem d - '
                          f'zła wartość, powinna być między {lon_min} a {lon_max}, a wynosi: {d}.')
            is_valid = False
        if not lon_min <= e <= lon_max:
            errors.append(f'Problem z podpolem e - '
                          f'zła wartość, powinna być między {lon_min} a {lon_max}, a wynosi: {e}.')
            is_valid = False
        if not lat_min <= f <= lat_max:
            errors.append(f'Problem z podpolem f - '
                          f'zła wartość, powinna być między {lat_min} a {lat_max}, a wynosi: {f}.')
            is_valid = False
        if not lat_min <= g <= lat_max:
            errors.append(f'Problem z podpolem g - '
                          f'zła wartość, powinna być między {lat_min} a {lat_max}, a wynosi: {g}.')
            is_valid = False

        # check if correct bbox
        if not d <= e:
            errors.append(f'Problem z podpolami d i e - '
                          f'wartość podpola d powinna być mniejsza od e lub równa e,'
                          f'tymczasem {d=} {e=}.')
            is_valid = False
        if not f >= g:
            errors.append(f'Problem z podpolami f i g - '
                          f'wartość podpola f powinna być większa od g lub równa g,'
                          f'tymczasem {f=} {g=}.')
            is_valid = False

        # add warning - should it actually be bbox at all?
        if not d == e or not f == g:
            errors.append(f'Ostrzeżenie: to nie jest punkt, tylko inny kształt (prostokąt, trójkąt lub linia). '
                          f'Czy na pewno o to chodziło? - '
                          f'{d=}, {e=}, {f=}, {g=}.')
            is_valid = False

    if not is_valid:
        errors_newlined = '\n'.join(f'    {error}' for error in errors)
        message = f'{rec_id_009}\t{rec_id_001}\t{rcd_name}\n' \
                  f'{errors_newlined}\n'
        log_to_file('geographical_descriptors_errors.txt', message)

    return is_valid


def dms_to_decimal(single_coord):
    hemisphere = single_coord[0]
    d = single_coord[1:4]
    m = single_coord[4:6]
    s = single_coord[6:]
    sign = 1 if hemisphere in ['N', 'E'] else -1
    return (int(d) + int(m) / 60 + int(s) / 3600) * sign


def main_loop(marc_in):
    valid_geo_count = 0
    invalid_geo_count = 0

    with open(marc_in, 'rb') as fp:
        rdr = MARCReader(fp, to_unicode=True, force_utf8=True, utf8_handling='ignore', permissive=True)

        for rcd in tqdm(rdr):
            id_001 = rcd.get_fields('001')[0].value() if rcd.get_fields('001') else None
            id_009 = rcd.get_fields('009')[0].value() if rcd.get_fields('009') else None
            rcd_name = rcd.get_fields('151')[0].value() if rcd.get_fields('151') else None
            coords_034 = rcd.get_fields('034')[0] if rcd.get_fields('034') else None

            if coords_034 and id_001 and id_009 and rcd_name:
                if check_defg_034(id_001, id_009, rcd_name, coords_034):
                    valid_geo_count += 1
                else:
                    invalid_geo_count += 1

    return valid_geo_count, invalid_geo_count, invalid_geo_count / valid_geo_count


if __name__ == '__main__':

    marc_file_in = 'authorities-all.marc'
    val, inval, ratio = main_loop(marc_file_in)

    print(val, inval, ratio)
