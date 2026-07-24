# BoukenshaLoader resolves which step folder to load from, then boots the REPL.
#
# Two independent settings are resolved, each with its own precedence:
#
#   lib path (which *step* to load):
#     1. BOUKENSHA_PATH environment variable
#     2. `path=` line in ~/.boukensharc (or the whole file, for the legacy
#        bare-path format — see parse_rc)
#     3. The lib/ directory bundled inside this gem (step 8 — the latest release)
#
#   config directory (settings.yaml, .env, system.md):
#     1. BOUKENSHA_DIR environment variable
#     2. `dir=` line in ~/.boukensharc
#     3. ~/.boukensha (Config's own default — the loader does nothing, and
#        Config.new resolves this itself)
#
# ~/.boukensharc format:
#   Either a bare path on its own (legacy, treated as `path=`):
#     echo ~/Sites/boukensha/08_the_repl_loop > ~/.boukensharc
#   Or key=value lines, one setting per line:
#     path=~/Sites/boukensha/08_the_repl_loop
#     dir=~/projects/mybot/.boukensha
#
# Examples:
#   boukensha                                                              # uses bundled lib + ~/.boukensha
#   BOUKENSHA_PATH=~/Sites/boukensha/04_api_client boukensha              # loads step 4
#   BOUKENSHA_DIR=~/projects/mybot/.boukensha boukensha                   # custom config dir
#   echo ~/Sites/boukensha/08_the_repl_loop > ~/.boukensharc && boukensha # permanent step default
module BoukenshaLoader
  # Absolute path to this gem's own bundled boukensha lib.
  BUNDLED_LIB = File.expand_path("../boukensha.rb", __FILE__)

  # Reads ~/.boukensharc and returns a { "path" => ..., "dir" => ... } hash
  # (only the keys actually present). Supports two formats:
  #   - key=value lines (any subset of "path"/"dir", in any order)
  #   - a single bare path with no "=" anywhere in the file (legacy format,
  #     treated as if it were `path=<that value>`)
  def self.parse_rc
    rc = File.expand_path("~/.boukensharc")
    return {} unless File.exist?(rc)

    lines = File.read(rc).lines.map(&:strip).reject(&:empty?)
    return {} if lines.empty?

    if lines.none? { |line| line.include?("=") }
      return { "path" => lines.first }
    end

    lines.each_with_object({}) do |line, settings|
      key, value = line.split("=", 2)
      next unless key && value

      settings[key.strip] = value.strip
    end
  end

  def self.resolve
    rc = parse_rc

    # BOUKENSHA_DIR: env var wins, then ~/.boukensharc's `dir=`, then
    # Config's own default (nothing to do here in that case).
    if !ENV["BOUKENSHA_DIR"] && rc["dir"] && !rc["dir"].empty?
      ENV["BOUKENSHA_DIR"] = File.expand_path(rc["dir"])
    end

    # 1. Env var wins.
    if ENV["BOUKENSHA_PATH"]
      dir  = File.expand_path(ENV["BOUKENSHA_PATH"])
      main = File.join(dir, "lib", "boukensha.rb")
      return main if File.exist?(main)

      abort <<~MSG
        boukensha: BOUKENSHA_PATH is set but no lib/boukensha.rb found at:
               #{dir}
               Make sure BOUKENSHA_PATH points to a step folder, e.g.:
               BOUKENSHA_PATH=~/Sites/boukensha/07_the_repl_loop boukensha
      MSG
    end

    # 2. ~/.boukensharc's `path=` (or legacy bare-path format)
    if rc["path"] && !rc["path"].empty?
      dir  = rc["path"]
      main = File.join(File.expand_path(dir), "lib", "boukensha.rb")
      return main if File.exist?(main)

      abort <<~MSG
        boukensha: ~/.boukensharc points to #{dir}
               but no lib/boukensha.rb was found there.
               Update ~/.boukensharc or remove it to use the bundled default.
      MSG
    end

    # 3. Bundled default.
    BUNDLED_LIB
  end

  def self.load_and_start_repl
    main = resolve
    step_dir = File.dirname(File.dirname(main))

    if ENV["BOUKENSHA_DEBUG"]
      puts "[boukensha] loading from: #{step_dir}"
      puts "[boukensha] config dir: #{ENV["BOUKENSHA_DIR"]}" if ENV["BOUKENSHA_DIR"]
    end

    require main

    unless Boukensha.respond_to?(:repl)
      abort <<~MSG
        boukensha: the step at #{step_dir}
               does not support the interactive REPL (added in step 7).
               Run its examples directly, e.g.:
                 ruby #{step_dir}/examples/*.rb
               Or point BOUKENSHA_PATH at step 7 or later.
      MSG
    end

    Boukensha.repl
  end
end
