
#version 330 core
#define version_set 330
#define M_PI 3.1415926535897932384626433832795

vec2 az_to_polar(vec2 az)
{
    vec2 latlon;
    latlon.x = -sqrt((az.x*az.x)+(az.y*az.y)) * M_PI + M_PI/2;
    latlon.y = atan(az.y,az.x);
    return latlon;    
}

vec2 cartesian_to_polar(vec3 cartesian)
{
    vec3 norm_pos = normalize(cartesian);
    float lat = acos(norm_pos.z) - M_PI/2;
    float lon = atan(norm_pos.y, norm_pos.x);
    return vec2(lat, lon);
}



vec3 polar_to_azimuthal(vec2 polar)
{
    vec3 az;
    float lat = polar.x;
    float lon = polar.y;
    float r = (M_PI/2-lat)/M_PI;
    az.x = r * cos(lon);
    az.y = r * sin(lon);
    az.z = r;
    return az;
}



vec3 spherical_to_cartesian(vec2 latlon)
{
    // Convert a lat, lon co-ordinate to an a Cartesian x,y,z point on the unit sphere.
    vec3 cart;
    float lon, lat;
    lat = latlon.x;
    lon = latlon.y;
    lat += M_PI/2;
    float st = sin(lat);
    cart.x = cos(lon) * st;
    cart.y = sin(lon) * st;
    cart.z = -cos(lat);    
    return cart;
}   

vec3 polar_to_cartesian(vec2 latlon)
{
    return spherical_to_cartesian(latlon);
}


// From https://gist.github.com/neilmendoza/4512992
mat4 rotationMatrix(vec3 axis, float angle)
{
    axis = normalize(axis);
    float s = sin(angle);
    float c = cos(angle);
    float oc = 1.0 - c;
    
    return mat4(oc * axis.x * axis.x + c,           oc * axis.x * axis.y - axis.z * s,  oc * axis.z * axis.x + axis.y * s,  0.0,
                oc * axis.x * axis.y + axis.z * s,  oc * axis.y * axis.y + c,           oc * axis.y * axis.z - axis.x * s,  0.0,
                oc * axis.z * axis.x - axis.y * s,  oc * axis.y * axis.z + axis.x * s,  oc * axis.z * axis.z + c,           0.0,
                0.0,                                0.0,                                0.0,                                1.0);

                
}