package cutctx

import "fmt"

// HeadroomError represents an API error from the CutCtx proxy.
type HeadroomError struct {
	Code   int    `json:"code"`
	Path   string `json:"path,omitempty"`
	Detail string `json:"detail,omitempty"`
}

func (e *HeadroomError) Error() string {
	if e.Detail != "" {
		return fmt.Sprintf("cutctx: %s returned %d: %s", e.Path, e.Code, e.Detail)
	}
	return fmt.Sprintf("cutctx: %s returned status %d", e.Path, e.Code)
}
