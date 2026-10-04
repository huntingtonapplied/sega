#!/bin/bash
# ============================================================================
# SYSMON - Graph Rendering Library
# ============================================================================
# Time-series graphs and charts for terminal display
# Source this file: source "${SYSMON_LIB_DIR}/display/graphs.sh"
# ============================================================================

# Prevent double-sourcing
[[ -n "${SYSMON_GRAPHS_LOADED:-}" ]] && return 0
SYSMON_GRAPHS_LOADED=1

# ============================================================================
# GRAPH CHARACTERS
# ============================================================================

# Vertical bar characters (8 levels, bottom to top)
GRAPH_VBAR_CHARS='▁▂▃▄▅▆▇█'

# Horizontal bar characters
GRAPH_HBAR_FULL='█'
GRAPH_HBAR_HALF='▌'
GRAPH_HBAR_EMPTY='░'

# Line drawing characters
GRAPH_LINE_H='─'
GRAPH_LINE_V='│'
GRAPH_CORNER_BL='└'
GRAPH_CORNER_TL='┌'

# Braille characters for high-resolution graphs (optional)
# Each braille char is 2x4 dots, allowing 8 levels per column

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

# Find maximum value in array
array_max() {
    local -a arr=("$@")
    local max=0
    for v in "${arr[@]}"; do
        [[ -z "$v" || ! "$v" =~ ^[0-9]+$ ]] && continue
        ((v > max)) && max=$v
    done
    echo "$max"
}

# Find minimum value in array
array_min() {
    local -a arr=("$@")
    local min=999999
    for v in "${arr[@]}"; do
        [[ -z "$v" || ! "$v" =~ ^[0-9]+$ ]] && continue
        ((v < min)) && min=$v
    done
    ((min == 999999)) && min=0
    echo "$min"
}

# Normalize array values to range 0-max_level
normalize_array() {
    local max_level="$1"
    shift
    local -a arr=("$@")

    local max=$(array_max "${arr[@]}")
    local min=$(array_min "${arr[@]}")
    local range=$((max - min))
    ((range == 0)) && range=1

    local -a normalized=()
    for v in "${arr[@]}"; do
        if [[ -z "$v" || ! "$v" =~ ^[0-9]+$ ]]; then
            normalized+=(0)
        else
            local norm=$(( (v - min) * max_level / range ))
            ((norm < 0)) && norm=0
            ((norm > max_level)) && norm=$max_level
            normalized+=($norm)
        fi
    done

    echo "${normalized[@]}"
}

# Resample array to target width (simple averaging)
resample_array() {
    local target_width="$1"
    shift
    local -a arr=("$@")
    local src_len=${#arr[@]}

    if ((src_len <= target_width)); then
        echo "${arr[@]}"
        return
    fi

    local -a result=()
    local bucket_size=$((src_len / target_width))
    ((bucket_size < 1)) && bucket_size=1

    local i=0
    while ((i < src_len)); do
        local sum=0 count=0
        for ((j=0; j<bucket_size && i+j<src_len; j++)); do
            local v="${arr[$((i+j))]}"
            if [[ "$v" =~ ^[0-9]+$ ]]; then
                ((sum += v))
                ((count++))
            fi
        done
        ((count > 0)) && result+=($((sum / count))) || result+=(0)
        ((i += bucket_size))
    done

    echo "${result[@]}"
}

# ============================================================================
# VERTICAL BAR GRAPH (Sparkline Style)
# ============================================================================

# Render a single-row sparkline from values
# Usage: render_sparkline width values...
# Returns: ▁▂▃▄▅▆▇█▆▄▂
render_sparkline_sized() {
    local width="$1"
    shift
    local -a values=("$@")

    # Resample to fit width
    local -a resampled=($(resample_array "$width" "${values[@]}"))

    # Normalize to 0-7 (8 levels)
    local -a normalized=($(normalize_array 7 "${resampled[@]}"))

    # Render
    local result=""
    for level in "${normalized[@]}"; do
        result+="${GRAPH_VBAR_CHARS:$level:1}"
    done

    echo -n "$result"
}

# ============================================================================
# MULTI-ROW VERTICAL BAR GRAPH
# ============================================================================

# Render a multi-row bar graph
# Usage: render_bar_graph height width max_value values...
# Output: Multiple lines forming a bar graph
render_bar_graph() {
    local height="$1"
    local width="$2"
    local max_val="$3"
    shift 3
    local -a values=("$@")

    # Resample to fit width
    local -a resampled=($(resample_array "$width" "${values[@]}"))

    # Auto-detect max if not provided or 0
    ((max_val <= 0)) && max_val=$(array_max "${resampled[@]}")
    ((max_val <= 0)) && max_val=100

    # Render each row from top to bottom
    local -a lines=()
    for ((row=height; row>=1; row--)); do
        local threshold=$((row * max_val / height))
        local line=""

        for v in "${resampled[@]}"; do
            [[ -z "$v" || ! "$v" =~ ^[0-9]+$ ]] && v=0
            if ((v >= threshold)); then
                line+="█"
            elif ((v >= threshold - max_val/height/2)); then
                line+="▄"
            else
                line+=" "
            fi
        done

        lines+=("$line")
    done

    # Output lines
    for line in "${lines[@]}"; do
        echo "$line"
    done
}

# ============================================================================
# GRAPH WITH AXES AND LABELS
# ============================================================================

# Render a complete graph with Y-axis labels and title
# Usage: render_graph_panel title height width max_val color values...
render_graph_panel() {
    local title="$1"
    local height="$2"
    local width="$3"
    local max_val="$4"
    local color="$5"
    shift 5
    local -a values=("$@")

    local y_label_width=6
    local graph_width=$((width - y_label_width - 2))

    # Resample values
    local -a resampled=($(resample_array "$graph_width" "${values[@]}"))

    # Auto max
    ((max_val <= 0)) && max_val=$(array_max "${resampled[@]}")
    ((max_val <= 0)) && max_val=100

    # Calculate stats
    local stats=($(calc_stats "${resampled[@]}"))
    local avg="${stats[0]}" min="${stats[1]}" max="${stats[2]}"

    # Render each row
    for ((row=height; row>=1; row--)); do
        local y_val=$((row * max_val / height))
        local threshold=$((row * max_val / height))

        # Y-axis label (only show for certain rows)
        if ((row == height)); then
            printf "%4d%%│" "$max_val"
        elif ((row == height/2)); then
            printf "%4d%%│" "$((max_val/2))"
        elif ((row == 1)); then
            printf "   0%%│"
        else
            printf "     │"
        fi

        # Graph bars
        echo -en "$color"
        for v in "${resampled[@]}"; do
            [[ -z "$v" || ! "$v" =~ ^[0-9]+$ ]] && v=0
            if ((v >= threshold)); then
                echo -n "█"
            elif ((v >= threshold - max_val/height/2)); then
                echo -n "▄"
            else
                echo -n " "
            fi
        done
        echo -en "${NC}"
        echo ""
    done

    # X-axis
    printf "     └"
    printf '─%.0s' $(seq 1 $graph_width)
    echo ""

    # Stats line
    printf "      avg: %d%%  min: %d%%  max: %d%%" "$avg" "$min" "$max"
    echo ""
}

# ============================================================================
# HORIZONTAL BAR (for storage breakdown)
# ============================================================================

# Render a horizontal bar with label
# Usage: render_hbar label value max width [suffix]
render_hbar() {
    local label="$1"
    local value="$2"
    local max="$3"
    local width="$4"
    local suffix="${5:-}"

    local label_width=16
    local bar_width=$((width - label_width - 10))

    # Calculate fill
    local pct=0
    ((max > 0)) && pct=$((value * 100 / max))
    local filled=$((pct * bar_width / 100))
    local empty=$((bar_width - filled))

    # Color based on percentage
    local color="$GREEN"
    ((pct >= 75)) && color="$YELLOW"
    ((pct >= 90)) && color="$RED"

    # Render
    printf "  %-${label_width}s" "$label"
    echo -en "$color"
    printf '%*s' "$filled" '' | tr ' ' '█'
    echo -en "${NC}"
    printf '%*s' "$empty" '' | tr ' ' '░'
    printf "  %s" "$suffix"
    echo ""
}

# Render a simple size bar (no percentage, just visual)
# Usage: render_size_bar label size max_size width
render_size_bar() {
    local label="$1"
    local size="$2"
    local max_size="$3"
    local width="$4"

    local label_width=20
    local size_width=8
    local bar_width=$((width - label_width - size_width - 4))

    # Parse size to bytes for comparison
    local size_bytes=$(parse_size_to_bytes "$size")
    local max_bytes=$(parse_size_to_bytes "$max_size")

    # Calculate fill
    local filled=0
    if ((max_bytes > 0)); then
        filled=$((size_bytes * bar_width / max_bytes))
    fi
    ((filled > bar_width)) && filled=$bar_width
    local empty=$((bar_width - filled))

    # Render
    printf "  %-${label_width}s %${size_width}s  " "$label" "$size"
    echo -en "${CYAN}"
    printf '%*s' "$filled" '' | tr ' ' '█'
    echo -en "${NC}"
    printf '%*s' "$empty" '' | tr ' ' '░'
    echo ""
}

# Parse size string to bytes (approximate)
parse_size_to_bytes() {
    local size="$1"
    local num="${size%[KMGT]*}"
    num="${num%.*}"  # Remove decimal
    local unit="${size##*[0-9]}"
    unit="${unit##*.}"  # Remove leading dot if any

    case "$unit" in
        K|KB|k|kb) echo $((num * 1024)) ;;
        M|MB|m|mb) echo $((num * 1024 * 1024)) ;;
        G|GB|g|gb) echo $((num * 1024 * 1024 * 1024)) ;;
        T|TB|t|tb) echo $((num * 1024 * 1024 * 1024 * 1024)) ;;
        *) echo "$num" ;;
    esac
}

# ============================================================================
# COMPARISON GRAPH (Multiple Lines)
# ============================================================================

# Render overlapping line graph for comparison
# Usage: render_comparison_graph height width max_val label1 values1... -- label2 values2...
render_comparison_graph() {
    local height="$1"
    local width="$2"
    local max_val="$3"
    shift 3

    # Parse arguments (simplified - just 3 datasets)
    local -a values1=()
    local -a values2=()
    local -a values3=()
    local current=1

    for arg in "$@"; do
        if [[ "$arg" == "--" ]]; then
            ((current++))
            continue
        fi
        case $current in
            1) values1+=("$arg") ;;
            2) values2+=("$arg") ;;
            3) values3+=("$arg") ;;
        esac
    done

    # Resample all to same width
    local graph_width=$((width - 8))
    local -a r1=($(resample_array "$graph_width" "${values1[@]}"))
    local -a r2=($(resample_array "$graph_width" "${values2[@]}"))
    local -a r3=($(resample_array "$graph_width" "${values3[@]}"))

    # Find global max
    ((max_val <= 0)) && {
        local m1=$(array_max "${r1[@]}")
        local m2=$(array_max "${r2[@]}")
        local m3=$(array_max "${r3[@]}")
        max_val=$m1
        ((m2 > max_val)) && max_val=$m2
        ((m3 > max_val)) && max_val=$m3
    }
    ((max_val <= 0)) && max_val=100

    # Render rows
    for ((row=height; row>=1; row--)); do
        local threshold=$((row * max_val / height))

        # Y label
        if ((row == height)); then
            printf "%4d%%│" "$max_val"
        elif ((row == 1)); then
            printf "   0%%│"
        else
            printf "     │"
        fi

        # Render each column
        for ((col=0; col<graph_width; col++)); do
            local v1="${r1[$col]:-0}"
            local v2="${r2[$col]:-0}"
            local v3="${r3[$col]:-0}"

            local char=" "
            # Priority: show highest value, or combine
            if ((v1 >= threshold)); then
                char="█"
                echo -en "${GREEN}"
            elif ((v2 >= threshold)); then
                char="▓"
                echo -en "${YELLOW}"
            elif ((v3 >= threshold)); then
                char="░"
                echo -en "${CYAN}"
            fi
            echo -n "$char"
            echo -en "${NC}"
        done
        echo ""
    done

    # X axis
    printf "     └"
    printf '─%.0s' $(seq 1 $graph_width)
    echo ""
}

# ============================================================================
# TIME AXIS LABELS
# ============================================================================

# Generate time axis labels for a given range
# Usage: render_time_axis width range start_time
render_time_axis() {
    local width="$1"
    local range="$2"
    local end_time="${3:-$(date +%s)}"

    local label_width=6
    local graph_width=$((width - label_width - 2))

    printf "      "

    # Calculate time points
    local start_time
    case "$range" in
        5m)  start_time=$((end_time - 300)) ;;
        15m) start_time=$((end_time - 900)) ;;
        1h)  start_time=$((end_time - 3600)) ;;
        6h)  start_time=$((end_time - 21600)) ;;
        24h) start_time=$((end_time - 86400)) ;;
        *)   start_time=$((end_time - 900)) ;;
    esac

    # Show 5 time labels
    local interval=$(( (end_time - start_time) / 4 ))
    local positions=(0 $((graph_width/4)) $((graph_width/2)) $((graph_width*3/4)) $((graph_width-4)))
    local times=($start_time $((start_time + interval)) $((start_time + interval*2)) $((start_time + interval*3)) $end_time)

    local last_pos=0
    for i in 0 1 2 3 4; do
        local pos=${positions[$i]}
        local ts=${times[$i]}
        local label=$(date -d "@$ts" '+%H:%M' 2>/dev/null || date -r "$ts" '+%H:%M')

        # Print spaces to reach position
        local spaces=$((pos - last_pos))
        ((spaces > 0)) && printf '%*s' "$spaces" ''

        echo -n "$label"
        last_pos=$((pos + 5))
    done
    echo ""
}
