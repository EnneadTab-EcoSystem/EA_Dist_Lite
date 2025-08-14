#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InDesign Writer Helper Backend
Handles text frame extraction, navigation, and management.
"""

import os
import sys
import json
import logging
import win32com.client
from typing import List, Dict, Optional, Tuple, Any

class InDesignTextManager:
    """Manages InDesign text frames and navigation."""
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.app = None
        self.document = None
        self.text_frames = []
        self.current_frame_index = 0
        self.current_page_index = 0
        
    def _setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def connect_to_indesign(self) -> bool:
        """Connect to InDesign application."""
        try:
            # Try to connect to running instance first
            try:
                self.app = win32com.client.GetActiveObject("InDesign.Application")
                self.logger.info("Connected to running InDesign instance")
            except:
                # Create new instance
                self.app = win32com.client.Dispatch("InDesign.Application")
                self.logger.info("Created new InDesign instance")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to InDesign: {e}")
            return False
    
    def get_active_document(self) -> Optional[Dict]:
        """Get the currently active document."""
        if not self.app:
            return None
            
        try:
            self.document = self.app.ActiveDocument
            if self.document:
                return {
                    "name": self.document.Name,
                    "path": self.document.FilePath,
                    "full_path": os.path.join(self.document.FilePath, self.document.Name) if self.document.FilePath else None,
                    "pages_count": self.document.Pages.Count,
                    "text_frames_count": len(self.document.TextFrames),
                    "is_saved": self.document.Saved
                }
        except Exception as e:
            self.logger.error(f"Failed to get active document: {e}")
            
        return None
    
    def extract_text_frames(self) -> List[Dict]:
        """Extract all text frames from the document."""
        if not self.document:
            return []
            
        self.text_frames = []
        
        try:
            # Get all text frames
            frames = self.document.TextFrames
            
            for i, frame in enumerate(frames):
                try:
                    # Get frame information
                    frame_info = {
                        "index": i,
                        "name": frame.Name if hasattr(frame, 'Name') else f"TextFrame_{i}",
                        "page_number": self._get_page_number(frame),
                        "page_name": self._get_page_name(frame),
                        "bounds": self._get_frame_bounds(frame),
                        "text_content": self._get_text_content(frame),
                        "character_count": self._get_character_count(frame),
                        "word_count": self._get_word_count(frame),
                        "is_locked": frame.Locked if hasattr(frame, 'Locked') else False,
                        "is_hidden": frame.Hidden if hasattr(frame, 'Hidden') else False,
                        "parent_story": frame.ParentStory.Name if hasattr(frame, 'ParentStory') else None
                    }
                    
                    self.text_frames.append(frame_info)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to extract frame {i}: {e}")
                    continue
            
            self.logger.info(f"Extracted {len(self.text_frames)} text frames")
            return self.text_frames
            
        except Exception as e:
            self.logger.error(f"Failed to extract text frames: {e}")
            return []
    
    def _get_page_number(self, frame) -> int:
        """Get the page number for a text frame."""
        try:
            if hasattr(frame, 'ParentPage'):
                return frame.ParentPage.Name
            elif hasattr(frame, 'PageItems'):
                # Try to find the page through page items
                for page in self.document.Pages:
                    if frame in page.PageItems:
                        return page.Name
            return 1
        except:
            return 1
    
    def _get_page_name(self, frame) -> str:
        """Get the page name for a text frame."""
        try:
            if hasattr(frame, 'ParentPage'):
                return frame.ParentPage.Name
            elif hasattr(frame, 'PageItems'):
                for page in self.document.Pages:
                    if frame in page.PageItems:
                        return page.Name
            return "Page 1"
        except:
            return "Page 1"
    
    def _get_frame_bounds(self, frame) -> Dict:
        """Get the bounds of a text frame."""
        try:
            if hasattr(frame, 'GeometricBounds'):
                bounds = frame.GeometricBounds
                return {
                    "x1": bounds[0],
                    "y1": bounds[1], 
                    "x2": bounds[2],
                    "y2": bounds[3]
                }
            return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
        except:
            return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    
    def _get_text_content(self, frame) -> str:
        """Get the text content of a text frame."""
        try:
            if hasattr(frame, 'Contents'):
                return frame.Contents
            elif hasattr(frame, 'Texts'):
                texts = frame.Texts
                if texts.Count > 0:
                    return texts[0].Contents
            return ""
        except:
            return ""
    
    def _get_character_count(self, frame) -> int:
        """Get the character count of a text frame."""
        try:
            content = self._get_text_content(frame)
            return len(content)
        except:
            return 0
    
    def _get_word_count(self, frame) -> int:
        """Get the word count of a text frame."""
        try:
            content = self._get_text_content(frame)
            words = content.split()
            return len(words)
        except:
            return 0
    
    def get_current_frame(self) -> Optional[Dict]:
        """Get the currently selected text frame."""
        if not self.text_frames or self.current_frame_index >= len(self.text_frames):
            return None
        return self.text_frames[self.current_frame_index]
    
    def navigate_to_frame(self, frame_index: int) -> Optional[Dict]:
        """Navigate to a specific text frame."""
        if 0 <= frame_index < len(self.text_frames):
            self.current_frame_index = frame_index
            return self.text_frames[frame_index]
        return None
    
    def next_frame(self) -> Optional[Dict]:
        """Navigate to the next text frame."""
        if self.current_frame_index < len(self.text_frames) - 1:
            self.current_frame_index += 1
            return self.text_frames[self.current_frame_index]
        return None
    
    def previous_frame(self) -> Optional[Dict]:
        """Navigate to the previous text frame."""
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
            return self.text_frames[self.current_frame_index]
        return None
    
    def get_frames_by_page(self, page_name: str) -> List[Dict]:
        """Get all text frames on a specific page."""
        return [frame for frame in self.text_frames if frame["page_name"] == page_name]
    
    def get_page_names(self) -> List[str]:
        """Get all page names in the document."""
        page_names = set()
        for frame in self.text_frames:
            page_names.add(frame["page_name"])
        return sorted(list(page_names))
    
    def search_text(self, search_term: str) -> List[Dict]:
        """Search for text frames containing specific text."""
        results = []
        search_term_lower = search_term.lower()
        
        for frame in self.text_frames:
            if search_term_lower in frame["text_content"].lower():
                results.append(frame)
        
        return results
    
    def get_document_statistics(self) -> Dict:
        """Get document statistics."""
        if not self.text_frames:
            return {}
        
        total_characters = sum(frame["character_count"] for frame in self.text_frames)
        total_words = sum(frame["word_count"] for frame in self.text_frames)
        total_pages = len(self.get_page_names())
        
        return {
            "total_frames": len(self.text_frames),
            "total_characters": total_characters,
            "total_words": total_words,
            "total_pages": total_pages,
            "average_chars_per_frame": total_characters / len(self.text_frames) if self.text_frames else 0,
            "average_words_per_frame": total_words / len(self.text_frames) if self.text_frames else 0
        }
    
    def update_text_content(self, frame_index: int, new_content: str) -> bool:
        """Update the text content of a specific frame."""
        if not self.document or frame_index >= len(self.text_frames):
            return False
            
        try:
            frame = self.document.TextFrames[frame_index]
            if hasattr(frame, 'Contents'):
                frame.Contents = new_content
                # Update our local copy
                self.text_frames[frame_index]["text_content"] = new_content
                self.text_frames[frame_index]["character_count"] = len(new_content)
                self.text_frames[frame_index]["word_count"] = len(new_content.split())
                return True
        except Exception as e:
            self.logger.error(f"Failed to update text content: {e}")
            
        return False
