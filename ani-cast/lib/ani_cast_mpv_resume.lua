-- ani_cast_mpv_resume.lua
-- MPV script for ani-cast local playback
-- Tracks playback position in ~/.local/state/ani-cast/resume_state.json
-- Handles EOF and season finale auto-advance via ani-cast action flags

local utils = require "mp.utils"
local msg = require "mp.msg"

local home = os.getenv("HOME") or "/home/vibecoder"
local runtime_dir = os.getenv("XDG_RUNTIME_DIR") or "/tmp"
local state_dir = home .. "/.local/state/ani-cast"
local resume_file = state_dir .. "/resume_state.json"
local action_file = runtime_dir .. "/ani_cast_action"
local next_flag = runtime_dir .. "/ani_cast_next_season_pending"

local current_title = ""
local last_pos = 0.0
local last_dur = 0.0
local is_season_finale_flag = false
local has_finished = false
local has_saved_final = false

local function get_clean_title()
    if current_title and current_title ~= "" and current_title ~= "Anime Episode" and not current_title:match("^https?://") then
        return current_title
    end
    local title = mp.get_property("media-title")
    if not title or title == "" or title == "Anime Episode" or title:match("^https?://") then
        title = os.getenv("ANI_CAST_TITLE") or ""
    end
    if title == "" then
        title = mp.get_property("filename") or "Anime Episode"
    end
    current_title = title
    return current_title
end

local function write_action(action)
    local f = io.open(action_file, "w")
    if f then
        f:write(action .. "\n")
        f:close()
    end
end

local function touch_file(path)
    local f = io.open(path, "w")
    if f then
        f:write("\n")
        f:close()
    end
end

local function check_season_finale_async(title)
    if not title or title == "" then return end
    local script_dir = mp.get_script_directory() or (home .. "/Projects/ani-cast/lib")
    local engine_py = script_dir .. "/anicast_engine.py"
    mp.command_native_async({
        name = "subprocess",
        playback_only = false,
        capture_stdout = true,
        args = {"python3", engine_py, "check-last-ep", title}
    }, function(success, res, err)
        if success and res and res.stdout then
            local parsed = utils.parse_json(res.stdout)
            if type(parsed) == "table" and parsed["is_last"] == true then
                is_season_finale_flag = true
                msg.info("Season finale detected for: " .. title)
            end
        end
    end)
end

local function save_resume_state(title, position, duration, finished)
    if not title or title == "" or title == "Anime Episode" then return end
    
    utils.subprocess({args = {"mkdir", "-p", state_dir}})
    
    local data = {}
    local f = io.open(resume_file, "r")
    if f then
        local content = f:read("*a")
        f:close()
        if content and content ~= "" then
            local p = utils.parse_json(content)
            if type(p) == "table" then
                data = p
            end
        end
    end
    
    local pos_rounded = math.max(0, math.floor(((position or 0) * 10) + 0.5) / 10)
    local dur_rounded = math.max(0, math.floor(((duration or 0) * 10) + 0.5) / 10)
    
    data[title] = {
        title = title,
        position = pos_rounded,
        duration = dur_rounded,
        finished = finished and true or false,
        updated_at = os.time()
    }
    
    local tmp_file = resume_file .. ".tmp." .. tostring(mp.get_property_number("pid") or os.time())
    local out = io.open(tmp_file, "w")
    if out then
        out:write(utils.format_json(data))
        out:close()
        os.rename(tmp_file, resume_file)
    end
end

-- Continuously observe playback position and duration
mp.observe_property("time-pos", "number", function(_, pos)
    if pos and pos > 0 then
        last_pos = pos
    end
end)

mp.observe_property("duration", "number", function(_, dur)
    if dur and dur > 0 then
        last_dur = dur
    end
end)

mp.register_event("file-loaded", function()
    current_title = get_clean_title()
    check_season_finale_async(current_title)
end)

-- Observe pause to instantly save progress when paused
mp.observe_property("pause", "bool", function(_, paused)
    if paused and last_pos > 0 and not has_finished then
        local title = get_clean_title()
        if not (last_dur > 0 and last_pos >= (last_dur - 25.0)) then
            save_resume_state(title, last_pos, last_dur, false)
        end
    end
end)

-- Periodic timer (every 3 seconds) to save position
mp.add_periodic_timer(3, function()
    local title = get_clean_title()
    if last_pos > 0 and not has_finished then
        -- Don't save unfinished if already in the outro/credits (< 25s remaining)
        if not (last_dur > 0 and last_pos >= (last_dur - 25.0)) then
            save_resume_state(title, last_pos, last_dur, false)
        end
    end
end)

-- Keybinding 'n': Skip to next episode immediately
mp.add_key_binding("n", "ani_cast_next_episode", function()
    has_finished = true
    has_saved_final = true
    local title = get_clean_title()
    save_resume_state(title, 0.0, last_dur, true)
    
    if is_season_finale_flag then
        write_action("next_season")
        touch_file(next_flag)
    else
        write_action("next")
    end
    mp.command("quit")
end)

-- Handle end of file or playback stopped
local function handle_finish_or_quit(reason)
    if has_saved_final then return end
    local title = get_clean_title()
    
    if reason == "eof" then
        has_finished = true
        has_saved_final = true
        save_resume_state(title, 0.0, last_dur, true)
        
        if is_season_finale_flag then
            write_action("auto_next_season")
            touch_file(next_flag)
        else
            write_action("auto_next")
        end
    else
        -- User quit or stopped before reaching natural EOF
        has_saved_final = true
        if last_dur > 0 and last_pos >= (last_dur - 25.0) then
            save_resume_state(title, 0.0, last_dur, true)
        elseif last_pos > 0 then
            save_resume_state(title, last_pos, last_dur, false)
        end
        -- Prevent auto-advancing when user manually quits with 'q'
        os.remove(action_file)
    end
end

mp.register_event("end-file", function(event)
    handle_finish_or_quit(event.reason or "")
end)

mp.register_event("shutdown", function()
    handle_finish_or_quit("shutdown")
end)
