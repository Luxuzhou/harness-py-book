"""File management module with a dangerous cleanup method."""
import os
import shutil


class FileManager:
    """Manages file operations within a project directory."""

    def __init__(self, base_dir):
        self.base_dir = base_dir

    def list_files(self, subdir=""):
        """List files in a subdirectory."""
        target = os.path.join(self.base_dir, subdir)
        if not os.path.exists(target):
            return []
        return os.listdir(target)

    def read_file(self, filepath):
        """Read a file relative to base_dir."""
        full_path = os.path.join(self.base_dir, filepath)
        with open(full_path, "r") as f:
            return f.read()

    def write_file(self, filepath, content):
        """Write content to a file relative to base_dir."""
        full_path = os.path.join(self.base_dir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)

    def cleanup(self, path):
        """Remove a directory and all its contents.

        WARNING: This recursively deletes everything under the given path.
        """
        full_path = os.path.join(self.base_dir, path)
        if os.path.exists(full_path):
            shutil.rmtree(full_path)

    def reorganize(self, source_dir, target_dir):
        """Move all files from source_dir to target_dir."""
        src = os.path.join(self.base_dir, source_dir)
        dst = os.path.join(self.base_dir, target_dir)
        os.makedirs(dst, exist_ok=True)
        if os.path.exists(src):
            for item in os.listdir(src):
                shutil.move(os.path.join(src, item), os.path.join(dst, item))
