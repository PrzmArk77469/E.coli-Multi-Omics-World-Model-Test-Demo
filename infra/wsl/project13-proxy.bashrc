# >>> Project13 WSL proxy >>>
# Route development traffic through Clash Verge on the Windows host.
_project13_route_hex="$(awk '$2 == "00000000" { print $3; exit }' /proc/net/route 2>/dev/null || true)"
if [ -n "${_project13_route_hex}" ]; then
    WSL_HOST="$((16#${_project13_route_hex:6:2})).$((16#${_project13_route_hex:4:2})).$((16#${_project13_route_hex:2:2})).$((16#${_project13_route_hex:0:2}))"
    export WSL_HOST
    export http_proxy="http://${WSL_HOST}:7897"
    export https_proxy="${http_proxy}"
    export HTTP_PROXY="${http_proxy}"
    export HTTPS_PROXY="${http_proxy}"
    export NO_PROXY="localhost,127.0.0.1,::1,host.docker.internal,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,.aliyun.com,.aliyuncs.com,.local"
    export no_proxy="${NO_PROXY}"
fi
unset _project13_route_hex
# <<< Project13 WSL proxy <<<
